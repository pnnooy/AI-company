"""
rules.py — 规则引擎
==================
基于规则的决策映射：事件 + 当前状态 → 表情 + 灯光。

更新日期: 2026-06-04（适配新协议 v2.0）

这是 AI 引擎 V1 的核心逻辑，简单、可调试、确定性高。
后续 V2/V3 可在此基础上叠加更复杂的决策。
"""

import logging
from typing import Tuple, Optional

from comm.protocol import Expression, EventCode, NFCLevel, PoseState, TouchSide, TouchType

logger = logging.getLogger(__name__)


# ============================================================================
# 规则表
# ============================================================================

# 格式: (event_code, condition_fn, expression, R, G, B, duration_ms)
# 按优先级从高到低排列，匹配到第一条就执行

RULES = [
    # ── 姿态事件（最高优先级）────────────────────
    # (事件码,          条件函数,                                     表情,            R,   G,   B,  持续时间)
    (EventCode.POSE,    lambda e: e.pose.state == PoseState.FALL,    Expression.ANGRY,   255,   0,   0,  3000),
    (EventCode.POSE,    lambda e: e.pose.state == PoseState.SHAKE,   Expression.SURPRISE,255, 128,   0,  2000),

    # ── 触摸事件 ────────────────────────────────
    (EventCode.TOUCH,   lambda e: e.touch.side == TouchSide.LEFT and e.touch.type == TouchType.HOLD,   Expression.HAPPY,    0, 255,   0,  2000),
    (EventCode.TOUCH,   lambda e: e.touch.side == TouchSide.RIGHT and e.touch.type == TouchType.HOLD,  Expression.FOCUS,    0,   0, 255,  2000),
    (EventCode.TOUCH,   lambda e: e.touch.side == TouchSide.LEFT and e.touch.type == TouchType.TAP,    Expression.HAPPY,    0, 255, 100,  1500),
    (EventCode.TOUCH,   lambda e: e.touch.side == TouchSide.RIGHT and e.touch.type == TouchType.TAP,   Expression.SURPRISE,100,   0, 255,  1500),

    # ── NFC 喂食事件 ─────────────────────────────
    (EventCode.NFC,     lambda e: e.nfc.level == NFCLevel.FEAST,  Expression.LOVE,    255,  50, 150,  5000),
    (EventCode.NFC,     lambda e: e.nfc.level == NFCLevel.MEAL,   Expression.LOVE,    200,  50, 200,  4000),
    (EventCode.NFC,     lambda e: e.nfc.level == NFCLevel.SNACK,  Expression.HAPPY,   100, 200, 100,  3000),
    (EventCode.NFC,     lambda e: e.nfc.level == NFCLevel.TAP,    Expression.FOCUS,    50,  50, 255,  2000),
]


# ============================================================================
# NFC 等级 → 情绪提升映射
# ============================================================================

NFC_EMOTION_BOOST = {
    NFCLevel.TAP: 0.1,     # < 3秒
    NFCLevel.SNACK: 0.3,   # 3-10秒
    NFCLevel.MEAL: 0.5,    # 10-30秒
    NFCLevel.FEAST: 0.8,   # > 30秒
}

# 默认情绪提升（未识别的 NFC 等级）
DEFAULT_NFC_BOOST = 0.1


def get_nfc_emotion_boost(level: NFCLevel) -> float:
    """获取指定 NFC 等级对应的情绪提升值"""
    return NFC_EMOTION_BOOST.get(level, DEFAULT_NFC_BOOST)


# ============================================================================
# 决策函数
# ============================================================================

# 函数签名: (SensorEvent, emotion_value: float) → (Expression, (R, G, B), duration_ms)
# 返回 None 表示不产生决策输出

def decide(event, emotion_value: float = 0.5) -> Optional[Tuple[Expression, Tuple[int, int, int], int]]:
    """
    根据传感器事件和当前情绪值，决定输出。

    Args:
        event: SensorEvent 对象
        emotion_value: 当前情绪值 [0.0, 1.0]

    Returns:
        (expression, (R, G, B), duration_ms) 或 None
    """
    for event_code, condition, expr, r, g, b, dur in RULES:
        if event.event_code == event_code:
            try:
                if condition is None or condition(event):
                    logger.info(
                        f"规则匹配: {event_code.name} → {expr.name}, "
                        f"RGB=({r},{g},{b}), dur={dur}ms"
                    )
                    return expr, (r, g, b), dur
            except Exception:
                # 条件函数执行异常（如数据不完整），跳过
                continue

    logger.debug(f"无匹配规则: {event.event_code.name}")
    return None


def decide_expression_and_rgb(
    emotion_value: float,
    event_type: str = "idle"
) -> Tuple[Expression, Tuple[int, int, int]]:
    """
    根据情绪值决定表情和灯光（用于被动展示或事件触发时的辅助决策）。

    Args:
        emotion_value: 情绪值 [0.0 ~ 1.0]
        event_type: "idle" | "touch" | "nfc" | "alert" | "shake"

    Returns:
        (expression, (R, G, B))
    """
    if event_type == "alert":
        return Expression.ANGRY, (255, 0, 0)

    if event_type == "shake":
        return Expression.SURPRISE, (255, 128, 0)

    # 基于情绪值
    if emotion_value > 0.7:
        return Expression.HAPPY, (0, 255, 50)
    elif emotion_value > 0.4:
        return Expression.NORMAL, (50, 50, 100)
    elif emotion_value > 0.2:
        return Expression.SAD, (100, 50, 0)
    else:
        return Expression.ANGRY, (255, 20, 0)
