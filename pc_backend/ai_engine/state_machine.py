"""
state_machine.py — 情绪状态机
============================
管理机器人的情绪状态与状态转移。

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

logger = logging.getLogger("state_machine")


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


@dataclass
class MachineState:
    """状态机"""
    state: State = State.IDLE
    prev_state: State = State.IDLE
    last_event_time: int = 0         # 最后一次事件的时间戳 (ms)
    emotion_value: float = 0.5       # 情绪值 [0.0 ~ 1.0], 0=负面 1=正面
    emotion_decay: float = 0.001     # 情绪自然衰减速率 (每 ms)

    # 内部计数器
    _interaction_count: int = field(default=0, repr=False)

    def on_event(self, event_type: str, timestamp_ms: int) -> State:
        """
        处理一个输入事件，返回转移后的状态。

        Args:
            event_type: 事件类型字符串 (如 "touch_tap", "shake", "nfc_card")
            timestamp_ms: 事件时间戳 (毫秒)

        Returns:
            当前状态 (转移后)
        """
        self.last_event_time = timestamp_ms

        # ── ALERT 状态特殊处理 ──
        if event_type == "fall":
            if self.state != State.ALERT:
                self.prev_state = self.state
                self.state = State.ALERT
                logger.info(f"状态转移: {self.prev_state} → ALERT (fall)")
            return self.state

        if self.state == State.ALERT:
            # 从 ALERT 恢复
            logger.info(f"状态恢复: ALERT → {self.prev_state}")
            self.state = self.prev_state

        # ── 事件驱动的状态转移 ──
        if event_type in ("touch_tap", "touch_hold", "nfc_card"):
            self._interaction_count += 1
            if self.state == State.IDLE or self.state == State.SLEEP:
                self.state = State.ACTIVE
                logger.info(f"状态转移: IDLE/SLEEP → ACTIVE")
            elif self.state == State.ACTIVE:
                self.state = State.INTERACT
                logger.info(f"状态转移: ACTIVE → INTERACT")

        # ── 情绪值调整 ──
        self._adjust_emotion(event_type)

        return self.state

    def tick(self, timestamp_ms: int) -> State:
        """
        定时调用，处理超时自动转移。

        在主循环中以 ~100ms 间隔调用。
        """
        elapsed = timestamp_ms - self.last_event_time

        # 情绪自然衰减
        self.emotion_value = max(0.0, self.emotion_value - self.emotion_decay * 100)

        # 超时转移
        if self.state == State.INTERACT and elapsed > TIMEOUT_INTERACT_TO_ACTIVE:
            self.state = State.ACTIVE
            self._interaction_count = 0
            logger.info(f"超时转移: INTERACT → ACTIVE")

        elif self.state == State.ACTIVE and elapsed > TIMEOUT_ACTIVE_TO_IDLE:
            self.state = State.IDLE
            logger.info(f"超时转移: ACTIVE → IDLE")

        elif (self.state == State.IDLE or self.state == State.ACTIVE) \
                and elapsed > TIMEOUT_ACTIVE_TO_SLEEP:
            self.state = State.SLEEP
            logger.info(f"超时转移: → SLEEP")

        return self.state

    def _adjust_emotion(self, event_type: str):
        """根据事件调整情绪值"""
        adjustments = {
            "touch_tap": +0.05,
            "touch_hold": +0.03,
            "shake": -0.1,
            "fall": -0.3,
            "nfc_card": +0.08,
        }
        delta = adjustments.get(event_type, 0.0)
        self.emotion_value = max(0.0, min(1.0, self.emotion_value + delta))
        logger.debug(f"情绪值: {self.emotion_value:.3f} ({event_type}: {delta:+.3f})")
