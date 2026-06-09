"""
state_machine.py — 情绪状态机
============================
管理机器人的情绪状态与状态转移。

更新日期: 2026-06-04（适配新协议 v2.0）

状态转移图:
                  触摸/NFC
    IDLE ────────────────────→ ACTIVE ────────────→ INTERACT
     ↑                           ↑      30s无交互       │
     │                           └─────────────────────┘
     │ 5min无交互                      10s无交互
     ↓
   SLEEP ←── 姿态倾倒触发 ALERT ──→ 回到之前状态
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger(__name__)


class State(Enum):
    """系统状态"""
    IDLE = auto()       # 待机：等待用户交互
    ACTIVE = auto()     # 活跃：检测到用户存在
    INTERACT = auto()   # 交互中：正在响应用户输入
    SLEEP = auto()      # 休眠：长时间无人交互
    ALERT = auto()      # 告警：倾倒/异常事件


# 状态持续时间阈值 (毫秒)
TIMEOUT_ACTIVE_TO_IDLE = 5 * 60 * 1000     # 5 分钟无交互 → 待机
TIMEOUT_INTERACT_TO_ACTIVE = 30 * 1000      # 30 秒无新交互 → 活跃
TIMEOUT_ACTIVE_TO_SLEEP = 30 * 60 * 1000    # 30 分钟无交互 → 休眠

# 情绪调节参数
EMOTION_DECAY_PER_SEC = 0.001               # 每秒自然衰减
EMOTION_MAX = 1.0
EMOTION_MIN = 0.0


@dataclass
class MachineState:
    """状态机"""
    state: State = State.IDLE
    prev_state: State = State.IDLE
    last_event_time: int = 0         # 最后一次事件的时间戳 (ms)
    emotion_value: float = 0.5       # 情绪值 [0.0 ~ 1.0], 0=负面 1=正面

    # 内部计数器
    _interaction_count: int = field(default=0, repr=False)

    # ── 事件驱动入口（新协议适配）─────────────────

    def on_touch_event(self, timestamp_ms: int):
        """
        处理触摸事件。

        对应新协议 EventCode.TOUCH (0x10)
        """
        self._on_interaction("touch", timestamp_ms)
        self.add_emotion(0.05, timestamp_ms)

    def on_nfc_event(self, timestamp_ms: int):
        """
        处理 NFC 喂食事件。

        对应新协议 EventCode.NFC (0x11)
        情绪提升由调用方根据 NFC 等级决定，这里只做状态转移。
        """
        self._on_interaction("nfc", timestamp_ms)

    def on_alert_event(self, timestamp_ms: int):
        """
        处理告警事件（倾倒/异常）。

        对应新协议 EventCode.POSE (0x12) state=FALL
        """
        self.last_event_time = timestamp_ms
        if self.state != State.ALERT:
            self.prev_state = self.state
            self.state = State.ALERT
            logger.info(f"状态转移: {self.prev_state} → ALERT")
        self.add_emotion(-0.3, timestamp_ms)

    def on_shake_event(self, timestamp_ms: int):
        """
        处理摇晃事件。

        对应新协议 EventCode.POSE (0x12) state=SHAKE
        """
        self._on_interaction("shake", timestamp_ms)
        self.add_emotion(-0.1, timestamp_ms)

    def add_emotion(self, delta: float, timestamp_ms: int):
        """
        按 delta 调节情绪值。

        Args:
            delta: 情绪变化量，正=开心，负=不开心
            timestamp_ms: 时间戳
        """
        self.last_event_time = timestamp_ms
        self.emotion_value = max(EMOTION_MIN, min(EMOTION_MAX, self.emotion_value + delta))
        logger.debug(f"情绪值: {self.emotion_value:.3f} (delta={delta:+.3f})")

    # ── 内部方法 ─────────────────────────────────

    def _on_interaction(self, event_name: str, timestamp_ms: int):
        """统一处理交互事件的状态转移"""
        self.last_event_time = timestamp_ms

        # 从 ALERT 恢复
        if self.state == State.ALERT:
            logger.info(f"状态恢复: ALERT → {self.prev_state}")
            self.state = self.prev_state

        # 状态转移
        if self.state in (State.IDLE, State.SLEEP):
            self.state = State.ACTIVE
            logger.info(f"状态转移: IDLE/SLEEP → ACTIVE")
        elif self.state == State.ACTIVE:
            self.state = State.INTERACT
            self._interaction_count += 1
            logger.info(f"状态转移: ACTIVE → INTERACT")
        elif self.state == State.INTERACT:
            self._interaction_count += 1

    # ── 定时 tick ────────────────────────────────

    def tick(self, timestamp_ms: int) -> State:
        """
        定时调用，处理超时自动转移和情绪衰减。

        在主循环中以 ~100ms 间隔调用。

        Returns:
            当前状态
        """
        elapsed = timestamp_ms - self.last_event_time

        # 情绪自然衰减
        self.emotion_value = max(EMOTION_MIN, self.emotion_value - EMOTION_DECAY_PER_SEC * 100)

        # 超时转移
        if self.state == State.INTERACT and elapsed > TIMEOUT_INTERACT_TO_ACTIVE:
            self.state = State.ACTIVE
            self._interaction_count = 0
            logger.info(f"超时转移: INTERACT → ACTIVE")

        elif self.state == State.ACTIVE and elapsed > TIMEOUT_ACTIVE_TO_IDLE:
            self.state = State.IDLE
            logger.info(f"超时转移: ACTIVE → IDLE")

        elif (self.state in (State.IDLE, State.ACTIVE)
                and elapsed > TIMEOUT_ACTIVE_TO_SLEEP):
            self.state = State.SLEEP
            logger.info(f"超时转移: → SLEEP")

        return self.state

    # ── 向后兼容 ─────────────────────────────────

    def on_event(self, event_type: str, timestamp_ms: int) -> State:
        """
        处理输入事件（旧 API，保留兼容）。

        Args:
            event_type: "touch_tap", "touch_hold", "shake", "fall", "nfc_card"
            timestamp_ms: 时间戳 (ms)

        Returns:
            当前状态
        """
        if event_type == "fall":
            self.on_alert_event(timestamp_ms)
        elif event_type == "shake":
            self.on_shake_event(timestamp_ms)
        elif event_type in ("touch_tap", "touch_hold", "nfc_card"):
            self._on_interaction(event_type, timestamp_ms)
            # 向后兼容的情绪调节
            adjustments = {
                "touch_tap": 0.05,
                "touch_hold": 0.03,
                "shake": -0.1,
                "fall": -0.3,
                "nfc_card": 0.08,
            }
            delta = adjustments.get(event_type, 0.0)
            self.add_emotion(delta, timestamp_ms)
        return self.state
