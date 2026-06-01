"""
ai_engine — AI 决策引擎
======================
根据传感器输入 + 历史状态，决定机器人的表情与灯光输出。

模块：
- state_machine: 情绪状态机 (IDLE→ACTIVE→INTERACT→SLEEP→ALERT)
- rules: 基于规则的决策逻辑 (事件 → 表情/灯光映射)
- llm_client: 大模型 API 客户端 (V3 阶段接入)
"""
