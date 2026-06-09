"""
rules.py — 规则引擎
==================
基于规则的决策映射：事件 + 情绪值 → 表情 + 灯光。

更新日期: 2026-06-09（修复审查发现的问题 3：情绪值接入决策）

这是 AI 引擎 V1 的核心逻辑，简单、可调试、确定性高。
后续 V2/V3 可在此基础上叠加更复杂的决策。
"""

import logging
from typing import Tuple, Optional

from comm.protocol import Expression, EventCode, NFCLevel, PoseState, TouchSide, TouchType

logger = logging.getLogger(__name__)


# ============================================================================
# 规则表 — 基础映射（事件 → 表情/灯光）
# ============================================================================

# 格式: (event_code, condition_fn, expression, R, G, B, duration_ms)
# 按优先级从高到低排列，匹配到第一条就执行

RULES = [
    # ── 姿态事件（最高优先级）────────────────────
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
# 情绪值 → 表情修饰（问题 3）
# ============================================================================

# 高情绪时用更开心的表情替代，低情绪时用更沮丧的表情替代
# 仅修饰"中性"事件（触摸 TAP、NFC TAP/SNACK），不覆盖 FALL/SHAKE/FEAST/HOLD

_EMOTION_UPGRADE = {
    # 原表情 → 高情绪替代 (>0.7)
    Expression.FOCUS: Expression.HAPPY,
    Expression.SURPRISE: Expression.LOVE,
    Expression.HAPPY: Expression.LOVE,
    Expression.NORMAL: Expression.HAPPY,
    Expression.SAD: Expression.NORMAL,
}

_EMOTION_DOWNGRADE = {
    # 原表情 → 低情绪替代 (<0.3)
    Expression.FOCUS: Expression.SAD,
    Expression.SURPRISE: Expression.ANGRY,
    Expression.HAPPY: Expression.NORMAL,
    Expression.NORMAL: Expression.SAD,
    Expression.LOVE: Expression.HAPPY,
}


# ============================================================================
# NFC 等级 → 情绪提升映射
# ============================================================================

NFC_EMOTION_BOOST = {
    NFCLevel.TAP: 0.1,     # < 3秒
    NFCLevel.SNACK: 0.3,   # 3-10秒
    NFCLevel.MEAL: 0.5,    # 10-30秒
    NFCLevel.FEAST: 0.8,   # > 30秒
}

DEFAULT_NFC_BOOST = 0.1


def get_nfc_emotion_boost(level: NFCLevel) -> float:
    """获取指定 NFC 等级对应的情绪提升值"""
    return NFC_EMOTION_BOOST.get(level, DEFAULT_NFC_BOOST)


# ============================================================================
# 决策函数
# ============================================================================

def decide(event, emotion_value: float = 0.5) -> Optional[Tuple[Expression, Tuple[int, int, int], int]]:
    """
    根据传感器事件和当前情绪值，决定输出。

    问题3修复：情绪值现在会影响最终表情。
    - 高情绪 (>0.7)：升级表情（HAPPY→LOVE）
    - 低情绪 (<0.3)：降级表情（HAPPY→SAD）
    - 中等情绪：使用基础规则结果

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
                    # 情绪修饰
                    # 安抚事件（触摸/NFC）：只升级不降级，摸她永远不该生气
                    # 刺激事件（SHAKE/FALL）：情绪低时可能表现更差
                    original = expr
                    is_comfort = event_code in (EventCode.TOUCH, EventCode.NFC)

                    if emotion_value > 0.7 and expr in _EMOTION_UPGRADE:
                        expr = _EMOTION_UPGRADE[expr]
                    elif emotion_value < 0.3 and expr in _EMOTION_DOWNGRADE and not is_comfort:
                        expr = _EMOTION_DOWNGRADE[expr]

                    extra = ""
                    if expr != original:
                        extra = f" (emotion={emotion_value:.2f}, {original.name}→{expr.name})"

                    logger.info(
                        f"规则匹配: {event_code.name} → {expr.name}, "
                        f"RGB=({r},{g},{b}), dur={dur}ms{extra}"
                    )
                    return expr, (r, g, b), dur
            except Exception:
                continue

    logger.debug(f"无匹配规则: {event.event_code.name}")
    return None


def decide_by_emotion(emotion_value: float) -> Tuple[Expression, Tuple[int, int, int]]:
    """
    仅根据情绪值决定表情和灯光（用于无事件时的被动展示 / 空闲状态更新）。

    问题3修复：主循环定期调用此函数，让情绪值真正驱动表情变化。

    Args:
        emotion_value: 情绪值 [0.0 ~ 1.0]

    Returns:
        (expression, (R, G, B))
    """
    if emotion_value > 0.7:
        return Expression.HAPPY, (0, 255, 50)
    elif emotion_value > 0.5:
        return Expression.NORMAL, (50, 100, 150)
    elif emotion_value > 0.3:
        return Expression.SAD, (100, 80, 30)
    elif emotion_value > 0.15:
        return Expression.ANGRY, (200, 30, 0)
    else:
        return Expression.SLEEP, (10, 5, 30)
