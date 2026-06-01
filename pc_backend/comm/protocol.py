"""
protocol.py — 通信协议定义
=========================
定义 PC ↔ STM32 之间的二进制帧格式。

帧结构 (与 firmware/Drivers/Src/uart_comm.c 保持一致):
┌──────┬──────┬──────┬──────────┬──────┬──────┐
│ SYNC │ SYNC │ LEN  │ PAYLOAD  │ CRC  │ END  │
│ 0xA5 │ 0x5A │ 1B   │ 0~255 B  │ 1B   │ 0xEE │
└──────┴──────┴──────┴──────────┴──────┴──────┘

命令码 (CMD):
- 0x01: 设置表情
- 0x02: 设置 RGB LED
- 0x03: 查询传感器状态
- 0x04: 传感器事件上报 (STM32 → PC)
- 0x05: 心跳 / ACK
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


# ── 帧常量 ──────────────────────────────────────
SYNC_BYTE_0 = 0xA5
SYNC_BYTE_1 = 0x5A
END_BYTE = 0xEE
MAX_PAYLOAD = 255


class Cmd(IntEnum):
    """命令码"""
    SET_EXPRESSION = 0x01      # PC → STM32: 设置表情
    SET_LED = 0x02             # PC → STM32: 设置 RGB 灯
    QUERY_SENSOR = 0x03        # PC → STM32: 查询传感器
    SENSOR_EVENT = 0x04        # STM32 → PC: 传感器事件上报
    HEARTBEAT = 0x05           # 双向: 心跳/ACK


class Expression(IntEnum):
    """表情枚举 (与固件 expression_types.h 保持一致)"""
    NORMAL = 0
    HAPPY = 1
    FOCUS = 2
    ANGRY = 3
    SLEEP = 4
    SURPRISE = 5
    SAD = 6
    LOVE = 7


class SensorEventType(IntEnum):
    """传感器事件类型"""
    TOUCH_LEFT_TAP = 0x10
    TOUCH_LEFT_HOLD = 0x11
    TOUCH_RIGHT_TAP = 0x20
    TOUCH_RIGHT_HOLD = 0x21
    TOUCH_DOUBLE = 0x30
    SHAKE = 0x40
    FALL = 0x41
    NFC_CARD = 0x50


# ── 数据类 ──────────────────────────────────────

@dataclass
class Frame:
    """解析后的通信帧"""
    cmd: Cmd
    payload: bytes = field(default_factory=bytes)

    @classmethod
    def pack(cls, cmd: Cmd, payload: bytes = b"") -> bytes:
        """将命令和负载打包为二进制帧"""
        if len(payload) > MAX_PAYLOAD:
            raise ValueError(f"Payload too long: {len(payload)} > {MAX_PAYLOAD}")
        length = len(payload)
        body = bytes([cmd]) + payload
        crc = cls._calc_crc(body)
        return bytes([SYNC_BYTE_0, SYNC_BYTE_1, length]) + body + bytes([crc, END_BYTE])

    @classmethod
    def unpack(cls, data: bytes) -> Optional["Frame"]:
        """
        从字节流中解析一帧。
        返回 Frame 如果解析成功，否则返回 None。
        """
        if len(data) < 6:
            return None
        if data[0] != SYNC_BYTE_0 or data[1] != SYNC_BYTE_1:
            return None
        length = data[2]
        if len(data) < 6 + length:
            return None
        if data[5 + length] != END_BYTE:
            return None
        body = data[3 : 3 + length + 1]  # cmd + payload
        crc_received = data[3 + length + 1]
        if cls._calc_crc(body) != crc_received:
            return None
        return cls(cmd=Cmd(body[0]), payload=body[1:])

    @staticmethod
    def _calc_crc(data: bytes) -> int:
        """CRC-8 校验"""
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


@dataclass
class SensorEvent:
    """传感器事件"""
    event_type: SensorEventType
    value: int = 0          # 附加数值 (如 NFC 卡片 UID 的低字节)
    timestamp_ms: int = 0   # 事件时间戳


@dataclass
class DeviceStatus:
    """设备状态快照"""
    expression: Expression = Expression.NORMAL
    led_r: int = 0
    led_g: int = 0
    led_b: int = 0
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    touch_left: bool = False
    touch_right: bool = False
    nfc_uid: int = 0
