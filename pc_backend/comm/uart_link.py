"""
uart_link.py — 串口链路
======================
基于 pyserial 的 UART 收发封装。

负责:
- 打开/关闭串口
- 二进制帧的发送与接收
- 接收缓冲管理与帧同步
"""

import logging
import threading
from typing import Callable, Optional

import serial

from .protocol import Frame, Cmd, SYNC_BYTE_0, SYNC_BYTE_1, END_BYTE

logger = logging.getLogger("uart_link")


class UartLink:
    """串口链路管理器"""

    def __init__(self, port: str = "COM6", baud: int = 115200):
        self.port = port
        self.baud = baud
        self._ser: Optional[serial.Serial] = None
        self._rx_buffer = bytearray()
        self._running = False
        self._rx_thread: Optional[threading.Thread] = None
        self._frame_callback: Optional[Callable[[Frame], None]] = None

    # ── 生命周期 ────────────────────────────────

    def open(self) -> bool:
        """打开串口连接"""
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
            )
            logger.info(f"串口 {self.port} 打开成功 @ {self.baud} bps")
            return True
        except serial.SerialException as e:
            logger.error(f"串口打开失败: {e}")
            return False

    def close(self):
        """关闭串口连接"""
        self._running = False
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=2)
        if self._ser and self._ser.is_open:
            self._ser.close()
            logger.info(f"串口 {self.port} 已关闭")

    # ── 发送 ────────────────────────────────────

    def send_frame(self, frame: Frame) -> bool:
        """发送一帧数据"""
        if not self._ser or not self._ser.is_open:
            logger.error("串口未打开，无法发送")
            return False
        data = Frame.pack(frame.cmd, frame.payload)
        written = self._ser.write(data)
        return written == len(data)

    def send_command(self, cmd: Cmd, payload: bytes = b"") -> bool:
        """快捷发送命令"""
        return self.send_frame(Frame(cmd=cmd, payload=payload))

    # ── 接收 ────────────────────────────────────

    def on_frame(self, callback: Callable[[Frame], None]):
        """注册帧接收回调"""
        self._frame_callback = callback

    def start_receiving(self):
        """启动后台接收线程"""
        if self._running:
            return
        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()
        logger.info("接收线程已启动")

    def _rx_loop(self):
        """接收线程主循环"""
        while self._running:
            if not self._ser or not self._ser.is_open:
                continue
            try:
                if self._ser.in_waiting > 0:
                    chunk = self._ser.read(self._ser.in_waiting)
                    self._rx_buffer.extend(chunk)
                    self._parse_buffer()
            except serial.SerialException:
                logger.warning("串口读取异常")
                break

    def _parse_buffer(self):
        """从接收缓冲区中解析帧"""
        while len(self._rx_buffer) >= 6:
            # 寻找帧头
            if self._rx_buffer[0] != SYNC_BYTE_0 or self._rx_buffer[1] != SYNC_BYTE_1:
                # 跳过无效字节直到找到帧头
                try:
                    idx = self._rx_buffer.index(SYNC_BYTE_0)
                    if idx > 0:
                        logger.debug(f"跳过 {idx} 个无效字节")
                    del self._rx_buffer[:idx]
                except ValueError:
                    self._rx_buffer.clear()
                    return
                # 确保至少有 2 个字节来判断帧头
                if len(self._rx_buffer) < 2 or self._rx_buffer[1] != SYNC_BYTE_1:
                    del self._rx_buffer[:1]
                    continue

            length = self._rx_buffer[2]
            frame_total = 6 + length  # HEAD(2) + LEN(1) + BODY(1+payload) + CRC(1) + END(1)

            if len(self._rx_buffer) < frame_total:
                return  # 数据不够，等待更多字节

            if self._rx_buffer[frame_total - 1] != END_BYTE:
                del self._rx_buffer[:1]  # 帧尾不匹配，丢弃一个字节重试
                continue

            frame = Frame.unpack(bytes(self._rx_buffer[:frame_total]))
            if frame and self._frame_callback:
                self._frame_callback(frame)

            del self._rx_buffer[:frame_total]
