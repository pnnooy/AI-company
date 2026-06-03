# 角色 B：PC 后端全链路

> **负责人**: B
> **工期**: 预计 2-3 天
> **前置条件**: Python 3.8+, COM6 可用, 项目仓库已 clone

---

## 一、任务总览

你是整个系统的**大脑中枢**。你的代码连接板子（串口）和前端（Web API），中间跑 AI 决策。

```
STM32 传感器事件
       ↓ 串口字节流
  [你的代码开始]
       ↓
  uart_link.py    ← 收字节、拼帧、解析
       ↓
  main.py         ← 事件总线、主循环
       ↓
  state_machine.py ← 状态转移 + 情绪值
  rules.py         ← 事件→表情/灯光 决策
       ↓
  uart_link.py    ← 发帧、下发指令
       ↓
  STM32 执行 (LCD表情 + RGB灯光)
       ↓
  web_api.py      ← 暴露 REST API 给前端 (C 角色)
  [你的代码结束]
       ↓
  Web UI (C 角色的地盘)
```

---

## 二、模块清单与优先级

| 优先级 | 模块 | 文件 | 状态 | 工作量 |
|--------|------|------|------|--------|
| P0 | 协议对齐验证 | `comm/protocol.py` | 已写，需与 A 对测 | 0.5h |
| P0 | 串口链路联调 | `comm/uart_link.py` | 已写，需实测 | 1h |
| P1 | 主循环/事件总线 | `main.py` | 骨架，需补全 | 3h |
| P1 | 规则引擎接线 | `ai_engine/rules.py` | 已写，连上主循环即可 | 1h |
| P1 | 状态机接线 | `ai_engine/state_machine.py` | 已写，连上主循环即可 | 0.5h |
| P2 | Web API 服务 | `web_api.py` (新建) | 未开始 | 2h |
| P3 | 摄像头接入 | `camera/face_detect.py` | 已写，接入主循环 | 1h |
| P3 | LLM 客户端 | `ai_engine/llm_client.py` (新建) | 未开始 | 3h |

---

## 三、P0：协议对齐 + 串口链路联调

### 3.1 与 A 的协议确认

打开 `pc_backend/comm/protocol.py`，确认以下定义与 A 的固件 `uart_comm.h` **逐字节一致**：

```python
# 帧结构
SYNC_BYTE_0 = 0xA5
SYNC_BYTE_1 = 0x5A
END_BYTE = 0xEE
MAX_PAYLOAD = 32  # 不含 CMD，只算 data 部分

# 命令码 (PC → MCU)
class Cmd(IntEnum):
    SET_EXPRESSION = 0x01
    SET_LED = 0x02
    QUERY_SENSOR = 0x03
    HEARTBEAT = 0x04

# 事件码 (MCU → PC) — 需要新增！
class EventType(IntEnum):
    TOUCH = 0x10
    NFC_CARD = 0x11
    POSE = 0x12
    ACK = 0x05
```

**⚠️ 当前 protocol.py 的传感器事件码 (0x10~0x50 的子类型) 需要和 A 确认一致。**

### 3.2 联调前的自测

用虚拟串口或直接向板子发测试帧：

```python
# test_uart_tx.py — 快速测试发送
from comm.protocol import Frame, Cmd, Expression

# 构造一帧：设置表情 = HAPPY
frame = Frame.pack(Cmd.SET_EXPRESSION, bytes([Expression.HAPPY]))
print(frame.hex())  # 应输出: a55a0101010dee  (CRC 值看实际计算)
```

然后用 SSCOM 发给板子，观察 LCD 是否变化。

### 3.3 联调接收

```python
# test_uart_rx.py — 快速测试接收
from comm.uart_link import UartLink

link = UartLink("COM6", 115200)

def on_frame(frame):
    print(f"收到帧: CMD={frame.cmd.name}, payload={frame.payload.hex()}")

link.on_frame(on_frame)
link.open()
link.start_receiving()

# 然后手动触发板子触摸，看终端是否有输出
input("按回车退出...")
link.close()
```

**目标**：你摸一下板子 → 终端打印收到 `TOUCH` 事件。这就打通了。

---

## 四、P1：主循环 + 事件总线 + AI 引擎

### 4.1 架构设计

```
main.py (主循环, ~100ms tick)
  │
  ├─ UartLink (后台线程接收，事件入队)
  │     └─ on_frame() → event_queue.put(event)
  │
  ├─ CameraCapture (可选，后台线程采集)
  │     └─ 每 500ms 检测人脸 → event_queue.put(face_event)
  │
  ├─ 主循环 (每 100ms)
  │     │
  │     ├─ 从 event_queue 取所有待处理事件
  │     ├─ state_machine.on_event(event)
  │     ├─ state_machine.tick(now_ms)     ← 超时转移
  │     ├─ rules.decide(event, emotion)   ← 决策
  │     └─ uart_link.send_command(...)    ← 下发
  │
  └─ Web API 服务 (FastAPI 子线程)
        └─ 读取共享状态对象，暴露 REST 接口
```

### 4.2 main.py 完整实现

替换现有的占位 `main.py`：

```python
"""
Desktop Academic Assistant Robot - PC Backend
=============================================
主入口：串口通信、AI引擎、Web API
"""

import argparse
import logging
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from comm.uart_link import UartLink
from comm.protocol import Frame, Cmd, Expression, SensorEventType
from ai_engine.state_machine import MachineState, State as FsmState
from ai_engine.rules import decide, decide_by_emotion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

# ── 全局共享状态 (Web API 读取) ──

@dataclass
class SharedState:
    """所有模块共享的状态对象"""
    fsm: MachineState = field(default_factory=MachineState)
    current_expression: Expression = Expression.NORMAL
    current_rgb: tuple = (0, 0, 0)
    last_event: str = ""
    event_log: list = field(default_factory=list)  # 最近 50 条
    running: bool = True

state = SharedState()


def handle_sensor_event(event_type: SensorEventType, link: UartLink, timestamp_ms: int):
    """处理一个传感器事件：状态机 → 规则 → 下发指令"""
    
    # 1. 状态机
    fsm = state.fsm
    old_state = fsm.state
    new_state = fsm.on_event(event_type.name, timestamp_ms)
    
    # 2. 规则决策
    expr, rgb, duration = decide(event_type, fsm.emotion_value)
    
    # 3. 下发指令
    if expr != state.current_expression:
        link.send_command(Cmd.SET_EXPRESSION, bytes([int(expr)]))
        state.current_expression = expr
        logger.info(f"下发表情: {expr.name}")
    
    if rgb != state.current_rgb:
        link.send_command(Cmd.SET_LED, bytes(rgb))
        state.current_rgb = rgb
        logger.info(f"下发灯光: RGB={rgb}")
    
    # 4. 记录日志
    state.last_event = event_type.name
    entry = f"[{timestamp_ms}] {event_type.name}: expr={expr.name}, rgb={rgb}, state={new_state.name}"
    state.event_log.append(entry)
    if len(state.event_log) > 50:
        state.event_log.pop(0)


def main_loop(link: UartLink, event_queue: queue.Queue):
    """主循环：消费事件队列 + 定时 tick"""
    
    TICK_MS = 100  # 主循环周期
    last_tick = 0
    
    while state.running:
        now_ms = int(time.time() * 1000)
        
        # 处理所有待处理事件
        try:
            while True:
                event = event_queue.get_nowait()
                handle_sensor_event(event, link, now_ms)
        except queue.Empty:
            pass
        
        # 定时 tick (超时状态转移 + 情绪衰减)
        if now_ms - last_tick >= TICK_MS:
            last_tick = now_ms
            old_state = state.fsm.state
            new_state = state.fsm.tick(now_ms)
            
            # 状态变化时更新表情
            if new_state != old_state:
                expr, rgb = decide_by_emotion(state.fsm.emotion_value)
                link.send_command(Cmd.SET_EXPRESSION, bytes([int(expr)]))
                link.send_command(Cmd.SET_LED, bytes(rgb))
                state.current_expression = expr
                state.current_rgb = rgb
        
        time.sleep(0.01)  # 10ms 睡眠，避免 CPU 空转


def on_uart_frame(frame: Frame, event_queue: queue.Queue):
    """串口帧回调：把传感器事件转成内部事件入队"""
    from comm.protocol import Cmd as CmdEnum
    
    if frame.cmd == CmdEnum.SENSOR_EVENT:
        # 解析 payload: [event_type:1B][data...]
        if len(frame.payload) >= 1:
            evt = frame.payload[0]
            # 映射到 SensorEventType
            evt_map = {
                0x10: SensorEventType.TOUCH_LEFT_TAP,
                0x11: SensorEventType.TOUCH_LEFT_HOLD,
                0x20: SensorEventType.TOUCH_RIGHT_TAP,
                0x21: SensorEventType.TOUCH_RIGHT_HOLD,
                0x30: SensorEventType.TOUCH_DOUBLE,
                0x40: SensorEventType.SHAKE,
                0x41: SensorEventType.FALL,
                0x50: SensorEventType.NFC_CARD,
            }
            event_type = evt_map.get(evt, SensorEventType.TOUCH_LEFT_TAP)
            event_queue.put(event_type)
            logger.debug(f"事件入队: {event_type.name}")
    
    elif frame.cmd == CmdEnum.HEARTBEAT:
        logger.debug("收到心跳 ACK")


def start_web_api():
    """在后台线程启动 Web API (供 C 角色对接)"""
    try:
        from web_api import start_server
        start_server(state)
    except ImportError:
        logger.warning("web_api.py 未就绪，跳过 Web 服务启动")


def main():
    parser = argparse.ArgumentParser(description="桌面学术助手机器人 PC 后端")
    parser.add_argument("--port", default="COM6", help="串口号")
    parser.add_argument("--baud", type=int, default=115200, help="波特率")
    parser.add_argument("--no-web", action="store_true", help="禁用 Web API")
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("桌面学术助手机器人 - PC Backend 启动")
    logger.info(f"串口: {args.port} @ {args.baud} bps")
    logger.info("=" * 50)

    # 1. 串口
    link = UartLink(args.port, args.baud)
    if not link.open():
        logger.error("串口打开失败，退出")
        sys.exit(1)

    # 2. 事件队列
    event_queue = queue.Queue()
    link.on_frame(lambda frame: on_uart_frame(frame, event_queue))
    link.start_receiving()
    logger.info("串口接收已启动，等待事件...")

    # 3. Web API (后台)
    if not args.no_web:
        threading.Thread(target=start_web_api, daemon=True).start()

    # 4. 主循环
    def sig_handler(sig, frame):
        logger.info("收到退出信号")
        state.running = False
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        main_loop(link, event_queue)
    except KeyboardInterrupt:
        pass
    finally:
        link.close()
        logger.info("PC Backend 已退出")


if __name__ == "__main__":
    main()
```

### 4.3 协议映射修正

**⚠️ 当前 protocol.py 中的帧结构和事件码与固件不完全匹配。你需要与 A 协调，确保以下映射正确：**

```
固件事件码 (uart_comm.h)    →  PC 内部 SensorEventType
─────────────────────────────────────────────────────
UART_EVT_TOUCH (0x10)      →  解析 payload[0]=side, payload[1]=type
                               组合成 TOUCH_LEFT_TAP / TOUCH_RIGHT_HOLD 等
UART_EVT_NFC   (0x11)      →  NFC_CARD
UART_EVT_POSE  (0x12)      →  payload[0]=0→稳定, 1→FALL, 2→SHAKE
```

**建议**：在 `protocol.py` 中新增一个 `parse_sensor_event()` 函数，把固件的原始字节映射成标准的 `SensorEventType`。

---

## 五、P2：Web API 服务

### 5.1 新建 `pc_backend/web_api.py`

为 C 角色提供接口。安装依赖：`pip install fastapi uvicorn`

```python
"""
web_api.py — REST API 服务
=========================
为 Web 前端提供机器人状态查询和手动控制接口。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="桌面学术助手 API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 通过 start_server() 注入
_state = None


class StatusResponse(BaseModel):
    expression: str
    expression_id: int
    emotion: float
    rgb: list
    state: str
    last_event: str
    uptime_seconds: float


class CommandRequest(BaseModel):
    cmd: str  # "set_expression" | "set_rgb" | "set_state"
    value: int | list | None = None


@app.get("/api/status")
def get_status():
    """返回机器人当前完整状态"""
    fsm = _state.fsm
    return {
        "expression": _state.current_expression.name,
        "expression_id": int(_state.current_expression),
        "emotion": round(fsm.emotion_value, 3),
        "rgb": list(_state.current_rgb),
        "state": fsm.state.name,
        "last_event": _state.last_event,
    }


@app.get("/api/events")
def get_events(limit: int = 20):
    """返回最近的事件日志"""
    return _state.event_log[-limit:]


@app.post("/api/command")
def send_command(req: CommandRequest):
    """手动下发指令（预留，后续对接串口发送）"""
    # TODO: 对接 UartLink 发送
    return {"status": "ok", "cmd": req.cmd, "value": req.value}


def start_server(shared_state, host="0.0.0.0", port=8000):
    """启动 Web API 服务"""
    global _state
    _state = shared_state
    uvicorn.run(app, host=host, port=port, log_level="info")
```

### 5.2 与 C 的联调

C 可以完全用 mock 数据开发前端：

```python
# mock_state.py — C 开发时独立运行，不依赖串口
class MockState:
    current_expression = type('obj', (object,), {'name': 'HAPPY', '__int__': lambda self: 1})()
    current_rgb = (0, 255, 50)
    fsm = type('obj', (object,), {'emotion_value': 0.72, 'state': type('obj', (object,), {'name': 'ACTIVE'})()})()
    last_event = "TOUCH_LEFT_TAP"
    event_log = [
        "[1400] TOUCH_LEFT_TAP: expr=HAPPY, rgb=(0,255,50), state=ACTIVE",
        "[1395] NFC_CARD: expr=FOCUS, rgb=(50,50,255), state=INTERACT",
    ]
```

---

## 六、P3：摄像头 + LLM（可后续）

### 6.1 摄像头接入主循环

```python
# 在主循环中加：
if camera_enabled and now_ms - last_face_check >= 500:
    last_face_check = now_ms
    frame = camera.read()
    if frame is not None:
        has_face, count = face_detector.detect(frame)
        if has_face and not face_detected:
            face_detected = True
            event_queue.put(FACE_DETECTED_EVENT)
        elif not has_face and face_detected:
            face_detected = False
            event_queue.put(FACE_LOST_EVENT)
```

### 6.2 LLM 客户端

```python
# ai_engine/llm_client.py
import anthropic

client = anthropic.Anthropic()

def ask_llm(user_text: str, emotion_state: dict) -> dict:
    """调用 Claude API，返回结构化决策"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system="""你是桌面机器人的AI大脑。根据用户输入和当前情绪状态，
输出JSON格式决策：{"expression": "HAPPY|FOCUS|...", "rgb": [R,G,B], "reply": "回复文本"}""",
        messages=[{"role": "user", "content": user_text}],
    )
    import json
    return json.loads(response.content[0].text)
```

---

## 七、接口规范汇总

### 与 A (固件)
| 项目 | 约定 |
|------|------|
| 帧格式 | `[A5][5A][LEN][CMD+PAYLOAD][CRC-8][EE]` |
| CRC-8 | 多项式 0x07, MSB first |
| 最大payload | 32 字节 |
| 表情ID | 0=NORMAL, 1=HAPPY, 2=FOCUS, 3=ANGRY, 4=SLEEP, 5=SURPRISE, 6=SAD, 7=LOVE |
| 联调信号 | PC 发 `A5 5A 01 01 00 XX EE` → 板子切表情 |
| 事件上报 | 固件用 UART_SendEvent() 发 0x10/0x11/0x12 事件帧 |

### 与 C (Web UI)
| 项目 | 约定 |
|------|------|
| API 地址 | `http://localhost:8000` |
| 状态接口 | `GET /api/status` → JSON |
| 事件日志 | `GET /api/events?limit=20` → JSON array |
| 命令接口 | `POST /api/command` ← `{"cmd":"...","value":...}` |
| 实时推送 | 后续可加 WebSocket `ws://localhost:8000/ws` |

### 与 D (表情素材)
| 项目 | 约定 |
|------|------|
| 表情枚举值 | 0-7 对应 emo_normal ~ emo_love |
| 新增表情 | 需同步修改 `protocol.py` 的 `Expression` 枚举 + 固件 `expression_types.h` |

### 与 E (文档/演示)
| 项目 | 约定 |
|------|------|
| API 文档 | FastAPI 自动生成 `http://localhost:8000/docs` |
| 演示配合 | 联调时可配合录屏，展示终端日志 + 板子实际反应 |

---

## 八、完成标准

- [ ] `uart_link.py` 能收到板子发来的触摸事件（摸板子 → 终端有日志）
- [ ] `main.py` 主循环跑通（事件→状态机→规则→下发指令→板子响应）
- [ ] 串口命令能控制板子表情和灯光（发 SET_EXPR → LCD 变脸）
- [ ] `web_api.py` 启动，`GET /api/status` 返回正确 JSON
- [ ] 与 C 确认 API 格式，C 能拿到 mock 数据开发
- [ ] 与 A 完成联调（A 触发事件 → B 终端收到 → 下发响应 → A 板子执行）
- [ ] 代码提交到 GitHub feature 分支
