"""
uart_link.py — 串口链路层 + 帧解析器
===================================
基于 pyserial 的 UART 收发封装，使用 5 状态机解析 v2.0 协议帧。

更新日期: 2026-06-04（根据 A 完成的固件协议 v2.0 重写）

负责:
- 打开/关闭串口
- 二进制帧的发送与接收（新协议 v2.0）
- 5 状态机帧解析：WAIT_SYNC0 → WAIT_SYNC1 → GET_LEN → GET_BODY → GET_END
- 100ms 帧超时检测
- 错误统计
"""

import logging
import threading
import time
from typing import Callable, Optional

import serial

from .protocol import (
    Frame, calc_crc8,
    SYNC0, SYNC1, END_BYTE, FRAME_TIMEOUT_MS,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 帧解析器（5 状态机）
# ============================================================================

class FrameParser:
    """
    帧解析器（5 状态机）

    状态转换:
        WAIT_SYNC0 → WAIT_SYNC1 → GET_LEN → GET_BODY → GET_END → WAIT_SYNC0

    特性:
    - 连续 A5 同步头处理（防误触发）
    - LEN 边界检查 [1, 33]
    - CRC-8 校验
    - 100ms 帧超时检测
    - 错误统计
    """

    def __init__(self):
        self.state = 'WAIT_SYNC0'
        self.buffer = bytearray()   # 存储 [CMD+DATA+CRC]（LEN 字节）
        self.length = 0             # LEN = CMD + DATA + CRC
        self.last_byte_time = 0

        # 错误统计
        self.stats = {
            'invalid_len': 0,
            'crc_fail': 0,
            'end_byte_err': 0,
            'timeout': 0,
            'frames_received': 0,
        }

    def reset(self):
        """重置状态机"""
        self.state = 'WAIT_SYNC0'
        self.buffer.clear()
        self.length = 0

    def feed(self, byte: int) -> Optional[Frame]:
        """
        喂入一个字节，返回解析出的帧（如果有）

        状态转换与固件 uart_comm.c UART_ParseByte() 完全一致:
        WAIT_SYNC0 → WAIT_SYNC1 → GET_LEN → GET_BODY → GET_END → WAIT_SYNC0

        GET_BODY 读取 LEN 字节到 buffer = [CMD][DATA][CRC]
        GET_END 读取 END=0xEE, CRC 校验在 buffer 内完成

        Args:
            byte: 单个字节 (0-255)

        Returns:
            Frame 对象或 None
        """
        now_ms = int(time.time() * 1000)

        # 超时检测（WAIT_SYNC0 不触发超时，因为没有帧在进行中）
        if self.state != 'WAIT_SYNC0':
            if now_ms - self.last_byte_time > FRAME_TIMEOUT_MS:
                self.stats['timeout'] += 1
                self.reset()

        self.last_byte_time = now_ms

        # ── 状态机 (与固件 uart_comm.c 逐行对应) ──────────────

        if self.state == 'WAIT_SYNC0':
            if byte == SYNC0:           # 0xA5
                self.state = 'WAIT_SYNC1'

        elif self.state == 'WAIT_SYNC1':
            if byte == SYNC1:           # 0x5A
                self.state = 'GET_LEN'
                self.buffer.clear()
            elif byte == SYNC0:         # 连续 A5，保持在 WAIT_SYNC1
                pass
            else:
                self.state = 'WAIT_SYNC0'  # 不是 5A，重新找同步头

        elif self.state == 'GET_LEN':
            # LEN 范围 [2, 34] (CMD + DATA + CRC)
            # 与固件 pkt_len 一致
            if 2 <= byte <= 34:
                self.length = byte
                self.state = 'GET_BODY'
            else:
                self.stats['invalid_len'] += 1
                self.reset()

        elif self.state == 'GET_BODY':
            # buffer 存储 LEN 字节: [CMD][DATA...][CRC]
            self.buffer.append(byte)
            if len(self.buffer) >= self.length:
                self.state = 'GET_END'

        elif self.state == 'GET_END':
            # 注意：CRC 检查需要用到 self.length 和 self.buffer，
            # 所以 reset() 必须在 CRC 检查之后调用
            if byte == END_BYTE:        # 0xEE
                # CRC 校验: buffer = [CMD][DATA...][CRC]
                # 与固件一致: data_len = pkt_len - 1
                data_len = self.length - 1  # 去掉 CRC
                payload = self.buffer[:data_len]  # CMD + DATA
                crc_received = self.buffer[data_len]  # CRC 在 buffer 末尾
                crc_expected = calc_crc8(payload)

                if crc_received == crc_expected:
                    self.stats['frames_received'] += 1
                    cmd = payload[0]
                    data = bytes(payload[1:]) if len(payload) > 1 else b''
                    self.reset()
                    return Frame(cmd=cmd, data=data)
                else:
                    self.stats['crc_fail'] += 1
                    logger.debug(
                        f"CRC 失败: received=0x{crc_received:02X}, "
                        f"expected=0x{crc_expected:02X}"
                    )
            else:
                self.stats['end_byte_err'] += 1
            self.reset()

        return None

    def get_stats(self) -> dict:
        """获取错误统计快照"""
        return self.stats.copy()


# ============================================================================
# 串口链路管理器
# ============================================================================

class UartLink:
    """串口链路管理器"""

    def __init__(self, port: str = "COM6", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.parser = FrameParser()
        self.running = False
        self.rx_thread: Optional[threading.Thread] = None
        self.frame_callback: Optional[Callable[[Frame], None]] = None

    # ── 生命周期 ────────────────────────────────

    def open(self) -> bool:
        """打开串口连接"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
            )
            logger.info(f"串口 {self.port} 打开成功 @ {self.baudrate} bps")
            return True
        except serial.SerialException as e:
            logger.error(f"串口打开失败: {e}")
            return False

    def close(self):
        """关闭串口连接"""
        self.running = False
        if self.rx_thread and self.rx_thread.is_alive():
            self.rx_thread.join(timeout=1.0)
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info(f"串口 {self.port} 已关闭")

    # ── 发送 ────────────────────────────────────

    def send_command(self, cmd: int, data: bytes = b'') -> bool:
        """
        发送命令帧

        Args:
            cmd: 命令码（0x01-0x04，对应 Cmd 枚举）
            data: 数据部分（最多 32 字节）

        Returns:
            是否发送成功
        """
        if not self.serial or not self.serial.is_open:
            logger.error("串口未打开，无法发送")
            return False

        try:
            frame_bytes = Frame.pack(cmd, data)
            written = self.serial.write(frame_bytes)
            logger.debug(f"发送帧: {frame_bytes.hex()} ({written} bytes)")
            return written == len(frame_bytes)
        except (ValueError, serial.SerialException) as e:
            logger.error(f"发送失败: {e}")
            return False

    def send_frame(self, frame: Frame) -> bool:
        """发送 Frame 对象（向后兼容）"""
        return self.send_command(frame.cmd, frame.data)

    # ── 接收 ────────────────────────────────────

    def on_frame(self, callback: Callable[[Frame], None]):
        """注册帧接收回调"""
        self.frame_callback = callback

    def start_receiving(self):
        """启动后台接收线程"""
        if self.running:
            logger.warning("接收线程已在运行")
            return
        self.running = True
        self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self.rx_thread.start()
        logger.info("接收线程已启动")

    def _rx_loop(self):
        """接收线程主循环"""
        while self.running:
            if not self.serial or not self.serial.is_open:
                time.sleep(0.1)
                continue
            try:
                if self.serial.in_waiting > 0:
                    byte = self.serial.read(1)[0]
                    frame = self.parser.feed(byte)

                    if frame and self.frame_callback:
                        self.frame_callback(frame)
                else:
                    time.sleep(0.001)  # 1ms 空闲等待
            except serial.SerialException as e:
                logger.warning(f"串口读取异常: {e}")
                break

    # ── 统计 ────────────────────────────────────

    def get_stats(self) -> dict:
        """获取帧解析器错误统计"""
        return self.parser.get_stats()
