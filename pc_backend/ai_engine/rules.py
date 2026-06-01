"""
rules.py — 规则引擎
==================
基于规则的决策映射：事件 + 当前状态 → 表情 + 灯光。

这是 AI 引擎 V1 的核心逻辑，简单、可调试、确定性高。
后续 V2/V3 可在此基础上叠加更复杂的决策。
"""

import logging
from typing import Tuple

from ..comm.protocol import Expression, SensorEventType

logger = logging.getLogger("rules")


# ── 规则表 ──────────────────────────────────────

# 格式: (事件类型, 情绪值范围) → (表情, RGB颜色, 持续时间ms)
# 按优先级从高到低排列，匹配到第一条就执行

RULES = [
    # (event_type,    emotion_min, emotion_max) → (expression,         R,   G,   B,  duration_ms)
    (SensorEventType.FALL,              None, None)  → (Expression.ANGRY,   255,  0,  0,  3000),
    (SensorEventType.SHAKE,             None, None)  → (Expression.SURPRISE,255,128,  0,  2000),
    (SensorEventType.TOUCH_DOUBLE,      None, None)  → (Expression.LOVE,    255, 50,150,  3000),
    (SensorEventType.TOUCH_LEFT_HOLD,   None, None)  → (Expression.HAPPY,    0,255,  0,  2000),
    (SensorEventType.TOUCH_RIGHT_HOLD,  None, None)  → (Expression.FOCUS,    0,  0,255,  2000),
    (SensorEventType.TOUCH_LEFT_TAP,    None, None)  → (Expression.HAPPY,    0,255,100,  1500),
    (SensorEventType.TOUCH_RIGHT_TAP,   None, None)  → (Expression.SURPRISE,100,  0,255,  1500),
    (SensorEventType.NFC_CARD,          None, None)  → (Expression.FOCUS,    50, 50,255,  5000),
]


def decide(event_type: SensorEventType, emotion_value: float = 0.5) -> Tuple[Expression, Tuple[int, int, int], int]:
    """
    根据事件类型和当前情绪值，决定输出。

    Args:
        event_type: 传感器事件类型
        emotion_value: 当前情绪值 [0.0, 1.0]

    Returns:
        (expression, (R, G, B), duration_ms)
    """
    for (evt, _, _), (expr, r, g, b, dur) in RULES:
        if evt == event_type:
            logger.info(f"规则匹配: {event_type.name} → {expr.name}, RGB=({r},{g},{b}), dur={dur}ms")
            return expr, (r, g, b), dur

    # 无匹配规则，返回默认
    logger.debug(f"无匹配规则: {event_type.name}, 返回默认")
    return Expression.NORMAL, (0, 0, 0), 0


def decide_by_emotion(emotion_value: float) -> Tuple[Expression, Tuple[int, int, int]]:
    """
    仅根据情绪值决定表情和灯光（用于无事件时的被动展示）。

    Args:
        emotion_value: 情绪值 [0.0 ~ 1.0]

    Returns:
        (expression, (R, G, B))
    """
    if emotion_value > 0.7:
        return Expression.HAPPY, (0, 255, 50)
    elif emotion_value > 0.4:
        return Expression.NORMAL, (50, 50, 100)
    elif emotion_value > 0.2:
        return Expression.SAD, (100, 50, 0)
    else:
        return Expression.ANGRY, (255, 20, 0)
