"""
Mock API Server + 静态页面托管
=============================
一键启动：提供模拟数据 API + 直接托管控制面板 HTML。

Usage:
    pip install fastapi uvicorn
    python mock_server.py

然后浏览器打开 http://localhost:8000 即可看到完整控制面板。
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn
import random
import time
import os

# 静态 HTML 页面路径
HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML = os.path.join(HERE, "index.html")

app = FastAPI(title="桌面学术助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class MockRobot:
    EXPRESSIONS = ["NORMAL", "HAPPY", "FOCUS", "ANGRY", "SLEEP", "SURPRISE", "SAD", "LOVE"]
    EXPR_NAMES_ZH = ["普通", "开心", "专注", "生气", "休眠", "惊讶", "难过", "爱心"]

    def __init__(self):
        self._expr_id = 0
        self._rgb = [0, 0, 0]
        self._emotion = 0.65
        self._state = "ACTIVE"
        self._last_event = "MOCK_STARTUP"
        self._event_log = [
            f"[{int(time.time())}] MOCK_STARTUP: Mock 服务器已启动",
            f"[{int(time.time())}] SYSTEM_INIT: 表情=NORMAL, 状态=ACTIVE",
        ]

    @property
    def expression(self): return self.EXPRESSIONS[self._expr_id]
    @property
    def expression_id(self): return self._expr_id
    @property
    def emotion(self):
        self._emotion += random.uniform(-0.03, 0.03)
        self._emotion = max(0.05, min(0.95, self._emotion))
        return round(self._emotion, 3)
    @property
    def rgb(self): return list(self._rgb)
    @property
    def state(self): return self._state
    @property
    def last_event(self): return self._last_event
    @property
    def event_log(self): return self._event_log

    def handle_command(self, cmd, value):
        if cmd == "set_expression":
            if isinstance(value, int) and 0 <= value < len(self.EXPRESSIONS):
                old = self.EXPRESSIONS[self._expr_id]
                self._expr_id = value
                self._add_event(f"CMD: 切换表情 {old} → {self.expression}")
                return True
        elif cmd == "set_rgb":
            if isinstance(value, list) and len(value) == 3:
                self._rgb = [int(v) for v in value]
                self._add_event(f"CMD: 设置灯光 RGB({self._rgb[0]},{self._rgb[1]},{self._rgb[2]})")
                return True
        self._add_event(f"CMD: 未知命令 {cmd}={value}")
        return False

    def random_event(self):
        if random.random() < 0.15:
            events = [
                ("TOUCH_LEFT_TAP", lambda: None),
                ("TOUCH_RIGHT_TAP", lambda: None),
                ("TILT_FORWARD", lambda: None),
                ("SHAKE", lambda: setattr(self, '_expr_id', 5)),
            ]
            name, action = random.choice(events)
            action()
            self._add_event(f"SENSOR: {name}")

    def _add_event(self, msg):
        ts = int(time.time())
        self._event_log.append(f"[{ts}] {msg}")
        self._last_event = msg
        if len(self._event_log) > 200:
            self._event_log = self._event_log[-200:]


mock = MockRobot()


# ---- 静态页面 ----

@app.get("/", response_class=HTMLResponse)
def index():
    """直接返回控制面板 HTML"""
    if os.path.exists(INDEX_HTML):
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html not found</h1>"


# ---- API ----

@app.get("/api/status")
def get_status():
    mock.random_event()
    return {
        "expression": mock.expression,
        "expression_id": mock.expression_id,
        "emotion": mock.emotion,
        "rgb": mock.rgb,
        "state": mock.state,
        "last_event": mock.last_event,
    }


@app.get("/api/events")
def get_events(limit: int = 20):
    return mock.event_log[-limit:]


@app.post("/api/command")
def post_command(cmd: dict):
    mock.handle_command(cmd.get("cmd"), cmd.get("value"))
    return {"status": "ok", "cmd": cmd.get("cmd"), "value": cmd.get("value")}


@app.post("/api/chat")
def chat(req: dict):
    """聊天接口 — 模拟 AI 回复"""
    msg = req.get("message", "")
    t = msg.lower() if msg else ""

    if "你好" in t or "hi" in t:
        reply = "你好！我是桌面学术助手 AI。有什么可以帮你的？"
    elif "表情" in t:
        reply = "当前支持 8 种表情：普通、开心、专注、生气、休眠、惊讶、难过、爱心。你可以点击按钮或按键盘 1-8 快速切换。"
    elif "灯" in t or "颜色" in t:
        reply = "灯光支持独立调节 R / G / B 三个通道（0-255），调整后点击「应用」发送到机器人。"
    elif "状态" in t:
        reply = f"当前状态：{mock.state}，表情：{mock.expression}，情绪值：{mock.emotion}，灯光：RGB({mock.rgb[0]},{mock.rgb[1]},{mock.rgb[2]})。"
    elif "帮助" in t or "help" in t:
        reply = "可用功能：\n• 表情切换 — 8 个按钮或快捷键 1-8\n• 灯光调节 — R/G/B 滑条\n• 状态监控 — 实时轮询\n• 事件日志 — 历史记录\n• AI 对话 — 当前窗口"
    elif "谢谢" in t or "thanks" in t:
        reply = "不客气！随时为你服务。"
    else:
        reply = f"收到你的消息：「{msg}」\n\n这是一个模拟回复。连接后端 LLM API 后，这里会返回真正的 AI 智能回复。"

    mock._add_event(f"CHAT: {msg[:40]}")
    return {"reply": reply, "mock": True}


@app.get("/api/health")
def health():
    return {"status": "healthy", "mock": True}


# ----

if __name__ == "__main__":
    print("=" * 50)
    print("  桌面学术助手 · Mock Server")
    print("=" * 50)
    print()
    print(f"  控制面板: http://localhost:8000")
    print(f"  API 文档: http://localhost:8000/docs")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")