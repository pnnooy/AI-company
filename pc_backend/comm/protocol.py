"""
protocol.py — 通信协议定义 (v2.0)
===============================
定义 PC ↔ STM32 之间的二进制帧格式，与固件 uart_comm.h/.c 完全对齐。

更新日期: 2026-06-04（根据 A 完成的固件协议 v2.0 重写）

协议规格:
- 帧格式: [A5][5A][LEN][CMD+DATA+CRC][EE]
- LEN: CMD + DATA + CRC 总长度，范围 [2, 34]
- CRC-8: 多项式 0x07，覆盖 [CMD+DATA]
- 超时: 100ms 帧接收超时

注意：LEN 包含 CRC 字节（与固件 uart_comm.c 接收端 pkt_buf 行为一致）

PC → MCU 命令码 (0x01-0x04):
- 0x01 SET_EXPR: [emo_id:1B]
- 0x02 SET_RGB:  [R:1B][G:1B][B:1B]
- 0x03 QUERY:    无 payload
- 0x04 HEARTBEAT: [seq:1B]

MCU → PC 事件码:
- 0x05 ACK:  [ack_cmd:1B][status:1B]
- 0x10 TOUCH: [side:1B][type:1B]
- 0x11 NFC:   [dur_low:1B][dur_high:1B][level:1B]
- 0x12 POSE:  [state:1B]
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


# ============================================================================
# 协议常量
# ============================================================================

SYNC0 = 0xA5
SYNC1 = 0x5A
END_BYTE = 0xEE
MAX_PAYLOAD = 34       # CMD(1) + DATA(最多32) + CRC(1)
FRAME_TIMEOUT_MS = 100  # 帧接收超时


# ============================================================================
# PC → MCU 命令码
# ============================================================================

class Cmd(IntEnum):
    """PC → MCU 命令码"""
    SET_EXPR = 0x01      # 设置表情: [emo_id:1B]
    SET_RGB = 0x02       # 设置 RGB 灯: [R:1B][G:1B][B:1B]
    QUERY = 0x03         # 查询状态: 无 payload
    HEARTBEAT = 0x04     # 心跳: [seq:1B]


# ============================================================================
# MCU → PC 事件码
# ============================================================================

class EventCode(IntEnum):
    """MCU → PC 事件码"""
    ACK = 0x05           # 命令响应: [ack_cmd:1B][status:1B]
    TOUCH = 0x10         # 触摸事件: [side:1B][type:1B]
    NFC = 0x11           # NFC 喂食: [dur_low:1B][dur_high:1B][level:1B]
    POSE = 0x12          # 姿态事件: [state:1B]


# ============================================================================
# 表情枚举（与固件 expression_types.h 保持一致）
# ============================================================================

class Expression(IntEnum):
    """表情 ID"""
    NORMAL = 0
    HAPPY = 1
    FOCUS = 2
    ANGRY = 3
    SLEEP = 4
    SURPRISE = 5
    SAD = 6
    LOVE = 7


# ============================================================================
# 触摸事件定义
# ============================================================================

class TouchSide(IntEnum):
    """触摸传感器位置"""
    LEFT = 0
    RIGHT = 1


class TouchType(IntEnum):
    """触摸类型（与固件 touch_sensor.h 一致）"""
    NONE = 0    # 无事件
    TAP = 1     # 轻触 < 1秒
    DOUBLE = 2  # 双击（两侧同时触摸）
    HOLD = 3    # 长按 > 1秒


# ============================================================================
# NFC 喂食等级
# ============================================================================

class NFCLevel(IntEnum):
    """NFC 喂食等级"""
    TAP = 0     # < 3秒
    SNACK = 1   # 3-10秒
    MEAL = 2    # 10-30秒
    FEAST = 3   # > 30秒


# ============================================================================
# 姿态状态
# ============================================================================

class PoseState(IntEnum):
    """姿态状态"""
    FALL = 1    # 倾倒/快速移动
    SHAKE = 2   # 摇晃


# ============================================================================
# CRC-8 计算
# ============================================================================

def calc_crc8(data: bytes) -> int:
    """
    CRC-8 校验（多项式 0x07）

    与固件端 uart_comm.c 的 CRC8_Calculate() 完全一致。

    Args:
        data: CMD + DATA 拼接的字节串

    Returns:
        CRC-8 校验码（0x00-0xFF）

    Examples:
        >>> calc_crc8(bytes([0x01, 0x01]))  # SET_EXPR HAPPY
        0x01
        >>> calc_crc8(bytes([0x02, 0xFF, 0x00, 0x00]))  # SET_RGB RED
        0xFE
    """
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
            crc &= 0xFF
    return crc


# ============================================================================
# 帧数据类
# ============================================================================

@dataclass
class Frame:
    """协议帧"""
    cmd: int           # 命令码/事件码
    data: bytes        # 数据部分（不含 CMD）

    @staticmethod
    def pack(cmd: int, data: bytes = b'') -> bytes:
        """
        打包完整帧

        Args:
            cmd: 命令码（0x01-0x04）
            data: 数据部分（最多 32 字节）

        Returns:
            完整帧字节串

        Raises:
            ValueError: data 超过 32 字节或 LEN 越界

        Examples:
            >>> Frame.pack(0x01, bytes([0x01])).hex()
            'a55a02010101ee'
        """
        if len(data) > 32:
            raise ValueError(f"Data too long: {len(data)} > 32")

        payload = bytes([cmd]) + data
        length = len(payload) + 1   # +1 for CRC byte

        if not (2 <= length <= 34):
            raise ValueError(f"Invalid LEN: {length} (must be [2, 34])")

        frame = bytes([
            SYNC0,              # 0xA5
            SYNC1,              # 0x5A
            length,             # LEN = CMD + DATA 总长
        ]) + payload + bytes([
            calc_crc8(payload),  # CRC-8 覆盖 CMD+DATA
            END_BYTE,            # 0xEE
        ])

        return frame

    def pack_bytes(self) -> bytes:
        """打包当前帧为字节串"""
        return Frame.pack(self.cmd, self.data)


# ============================================================================
# 事件解析类
# ============================================================================

@dataclass
class TouchEvent:
    """触摸事件"""
    side: TouchSide
    type: TouchType

    @staticmethod
    def parse(data: bytes) -> Optional['TouchEvent']:
        """解析触摸事件 payload: [side:1B][type:1B]"""
        if len(data) < 2:
            return None
        try:
            return TouchEvent(
                side=TouchSide(data[0]),
                type=TouchType(data[1])
            )
        except ValueError:
            return None


@dataclass
class NFCEvent:
    """NFC 喂食事件"""
    duration: int      # 喂食时长（秒）
    level: NFCLevel    # 喂食等级

    @staticmethod
    def parse(data: bytes) -> Optional['NFCEvent']:
        """
        解析 NFC 事件 payload: [dur_low:1B][dur_high:1B][level:1B]

        duration 为 16-bit 小端序
        """
        if len(data) < 3:
            return None
        try:
            duration = data[0] | (data[1] << 8)  # 16-bit 小端序
            level = NFCLevel(data[2])
            return NFCEvent(duration=duration, level=level)
        except ValueError:
            return None


@dataclass
class PoseEvent:
    """姿态事件"""
    state: PoseState

    @staticmethod
    def parse(data: bytes) -> Optional['PoseEvent']:
        """解析姿态事件 payload: [state:1B]"""
        if len(data) < 1:
            return None
        try:
            return PoseEvent(state=PoseState(data[0]))
        except ValueError:
            return None


@dataclass
class ACKEvent:
    """ACK 响应"""
    ack_cmd: int
    status: int

    @staticmethod
    def parse(data: bytes) -> Optional['ACKEvent']:
        """解析 ACK payload: [ack_cmd:1B][status:1B]"""
        if len(data) < 2:
            return None
        return ACKEvent(ack_cmd=data[0], status=data[1])


# ============================================================================
# 统一事件类
# ============================================================================

@dataclass
class SensorEvent:
    """统一的传感器事件"""
    event_code: EventCode
    touch: Optional[TouchEvent] = None
    nfc: Optional[NFCEvent] = None
    pose: Optional[PoseEvent] = None
    ack: Optional[ACKEvent] = None

    @staticmethod
    def from_frame(frame: Frame) -> Optional['SensorEvent']:
        """从帧解析传感器事件"""
        try:
            event_code = EventCode(frame.cmd)
        except ValueError:
            return None  # 不是有效的事件码（可能是命令码）

        event = SensorEvent(event_code=event_code)

        if event_code == EventCode.TOUCH:
            event.touch = TouchEvent.parse(frame.data)
        elif event_code == EventCode.NFC:
            event.nfc = NFCEvent.parse(frame.data)
        elif event_code == EventCode.POSE:
            event.pose = PoseEvent.parse(frame.data)
        elif event_code == EventCode.ACK:
            event.ack = ACKEvent.parse(frame.data)

        return event


# ============================================================================
# 向后兼容的别名（旧代码过渡用，后续可移除）
# ============================================================================

Cmd__SET_EXPRESSION = Cmd.SET_EXPR
Cmd__SET_LED = Cmd.SET_RGB
Cmd__QUERY_SENSOR = Cmd.QUERY
Cmd__HEARTBEAT = Cmd.HEARTBEAT
