"""
state_machine.py — 情绪状态机
============================
管理机器人的情绪状态与状态转移。

更新日期: 2026-06-09（修复审查发现的 5 个问题）

状态转移图:
                  触摸/NFC(安抚)
    IDLE ────────────────────→ ACTIVE ────────────→ INTERACT
     ↑                           ↑      30s无交互       │
     │                           └─────────────────────┘
     │ 5min无交互                      10s无交互
     ↓
   SLEEP ←── 姿态倾倒触发 ALERT ←── 只有触摸/NFC 可安抚恢复
                         ↑
                    SHAKE 不会解除 ALERT（问题1修复）
"""

import logging
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
EMOTION_DECAY_PER_SEC = 0.01                # 每秒自然衰减（问题2：改为合理速率）
EMOTION_MAX = 1.0
EMOTION_MIN = 0.0


@dataclass
class MachineState:
    """状态机"""
    state: State = State.IDLE
    prev_state: State = State.IDLE
    last_event_time: int = 0         # 最后一次事件的时间戳 (ms)
    emotion_value: float = 0.5       # 情绪值 [0.0 ~ 1.0], 0=负面 1=正面

    # 内部
    _interaction_count: int = field(default=0, repr=False)
    _last_tick_time: int = field(default=0, repr=False)   # 问题2：上次 tick 时间戳

    # ── 事件驱动入口 ──────────────────────────────

    def on_touch_event(self, timestamp_ms: int):
        """
        处理触摸事件（安抚动作，可解除 ALERT）。

        对应 EventCode.TOUCH (0x10)
        """
        self._on_comfort(timestamp_ms)
        self.add_emotion(0.05, timestamp_ms)

    def on_nfc_event(self, timestamp_ms: int, emotion_boost: float = 0.1):
        """
        处理 NFC 喂食事件（安抚动作，可解除 ALERT）。

        对应 EventCode.NFC (0x11)

        问题4修复：emotion_boost 内置，调用方无需重复调 add_emotion。
        """
        self._on_comfort(timestamp_ms)
        self.add_emotion(emotion_boost, timestamp_ms)

    def on_alert_event(self, timestamp_ms: int):
        """
        处理告警事件（倾倒）。

        对应 EventCode.POSE (0x12) state=FALL
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

        问题1修复：SHAKE 不会解除 ALERT。
        摇晃是"刺激"不是"安抚"，只有触摸/NFC 能安抚。

        对应 EventCode.POSE (0x12) state=SHAKE
        """
        self.last_event_time = timestamp_ms
        self.add_emotion(-0.02, timestamp_ms)

        # 状态转移（跳过 ALERT 恢复）
        if self.state == State.ALERT:
            # 保持 ALERT，摇晃不会安抚
            logger.debug(f"SHAKE while ALERT, staying alert")
        elif self.state in (State.IDLE, State.SLEEP):
            self.state = State.ACTIVE
            logger.info(f"状态转移: IDLE/SLEEP → ACTIVE (shake)")
        elif self.state == State.ACTIVE:
            self.state = State.INTERACT
            self._interaction_count += 1
            logger.info(f"状态转移: ACTIVE → INTERACT (shake)")
        elif self.state == State.INTERACT:
            self._interaction_count += 1

    def add_emotion(self, delta: float, timestamp_ms: int):
        """
        按 delta 调节情绪值。

        Args:
            delta: 情绪变化量，正=开心，负=不开心
            timestamp_ms: 时间戳 (ms)
        """
        self.last_event_time = timestamp_ms
        old = self.emotion_value
        self.emotion_value = max(EMOTION_MIN, min(EMOTION_MAX, self.emotion_value + delta))
        if abs(old - self.emotion_value) > 0.01:
            logger.debug(f"情绪值: {old:.3f} → {self.emotion_value:.3f} (delta={delta:+.3f})")

    # ── 内部方法 ─────────────────────────────────

    def _on_comfort(self, timestamp_ms: int):
        """安抚类事件（触摸/NFC）统一处理，从 ALERT 恢复"""
        self.last_event_time = timestamp_ms

        # 从 ALERT 恢复（仅安抚事件）
        if self.state == State.ALERT:
            logger.info(f"安抚恢复: ALERT → {self.prev_state}")
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

        应在主循环中周期性调用。

        问题2修复：基于实际时间差衰减，不再硬编码 100ms。
        """
        # 情绪衰减（基于实际时间差）
        if self._last_tick_time > 0:
            dt_sec = (timestamp_ms - self._last_tick_time) / 1000.0
            # 限制单次衰减不超过 10 秒（防止长时间未调用）
            dt_sec = min(dt_sec, 10.0)
            decay = EMOTION_DECAY_PER_SEC * dt_sec
            if decay > 0:
                self.emotion_value = max(EMOTION_MIN, self.emotion_value - decay)
        self._last_tick_time = timestamp_ms

        elapsed = timestamp_ms - self.last_event_time

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

    # ── 向后兼容（旧 API，保留）──────────────────

    def on_event(self, event_type: str, timestamp_ms: int) -> State:
        """处理输入事件（旧 API）"""
        if event_type == "fall":
            self.on_alert_event(timestamp_ms)
        elif event_type == "shake":
            self.on_shake_event(timestamp_ms)
        elif event_type in ("touch_tap", "touch_hold"):
            self._on_comfort(timestamp_ms)
            adjustments = {"touch_tap": 0.05, "touch_hold": 0.03}
            self.add_emotion(adjustments.get(event_type, 0.0), timestamp_ms)
        elif event_type == "nfc_card":
            self.on_nfc_event(timestamp_ms, 0.08)
        return self.state
