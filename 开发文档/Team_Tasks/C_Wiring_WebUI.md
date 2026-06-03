# 角色 C：硬件接线 + Web 前端

> **负责人**: C
> **工期**: 预计 2-3 天
> **前置条件**: 杜邦线、RC522 模块、Python 3.8+、浏览器

---

## 一、任务总览

你负责两个独立任务，按时间顺序：

| 阶段 | 任务 | 时间 | 依赖 |
|------|------|------|------|
| Day1 上午 | 硬件接线（NFC + 备线） | 1-2h | 无 |
| Day1 下午起 | Web 前端控制面板 | 2-3天 | 不依赖任何人，可 mock 开发 |

**接线做完后，你可以完全独立地做前端开发**，不需要等 A 或 B 完成。

---

## 二、阶段 1：硬件接线

### 2.1 NFC RC522 接线

RC522 模块通过杜邦线连接到 STM32 开发板。

| RC522 引脚 | 线色建议 | STM32 引脚 | 板子位置 |
|------------|----------|-----------|----------|
| VCC (3.3V) | 红 | 3.3V | 板子 3.3V 排针 |
| GND | 黑 | GND | 板子 GND 排针 |
| RST | 橙 | PA3 | GPIO 排针 |
| SDA (CS) | 黄 | PA4 | GPIO 排针 |
| SCK | 绿 | PA5 | SPI 排针 |
| MISO | 蓝 | PA6 | SPI 排针 |
| MOSI | 紫 | PA7 | SPI 排针 |
| IRQ | — | **不接** | RC522 不接中断脚 |

**接线要求**：
- 杜邦线尽量短（≤15cm），SPI 信号对线长敏感
- 母对母杜邦线，直接插 RC522 排针和 STM32 排针
- 用扎带或胶带把线束固定，避免晃动导致接触不良

### 2.2 接线验证

接线完毕后，配合 A 做验证：

1. A 烧录 NFC 测试固件
2. 串口工具（SSCOM）观察输出
3. 如果打印 `[NFC DBG] poll: card=1` 说明接线正确
4. 如果始终 `card=0`：
   - 检查每根线是否插紧
   - 万用表蜂鸣档测每根线通断
   - 重点检查 MISO/MOSI 是否交换（最常见的错误）

### 2.3 备线工作

预留一些杜邦线：
- 3 根母对母（备用，以防某根线接触不良）
- 2 根公对母（后续可能需要接额外的传感器）

### 2.4 接线完成后拍照

给每根线的连接处拍清晰照片，发给 E 用于文档和演示。

---

## 三、阶段 2：Web 前端控制面板

### 3.1 目标

做一个在浏览器中打开的机器人控制面板，功能包括：
- 实时显示机器人状态（表情、情绪值、灯光、系统状态）
- 手动控制面板（切换表情、调节灯光）
- 事件日志流

### 3.2 技术方案

```
后端: FastAPI (Python)        ← B 角色提供
前端: 纯 HTML + CSS + JS     ← 你负责
通信: HTTP REST API           ← B 角色定义接口格式
实时: 轮询 GET /api/status (每 500ms)
     后续升级为 WebSocket
```

**不需要**：React / Vue / npm / webpack。一个 HTML 文件 + 内嵌 CSS/JS 就够。

### 3.3 目录结构

```
pc_backend/
├── web_ui/
│   ├── index.html      ← 你写的主页面
│   ├── style.css       ← 样式（可选，也可内嵌在 HTML 中）
│   └── app.js          ← 逻辑（可选，也可内嵌在 HTML 中）
└── web_api.py          ← B 角色写的 API 服务
```

### 3.4 API 接口说明（与 B 约定）

B 的 `web_api.py` 提供以下接口：

```
GET  http://localhost:8000/api/status
响应:
{
    "expression": "HAPPY",       // 当前表情名称
    "expression_id": 1,          // 表情编号 0-7
    "emotion": 0.72,             // 情绪值 0.0~1.0
    "rgb": [0, 255, 50],         // RGB 颜色值
    "state": "ACTIVE",           // 系统状态: IDLE|ACTIVE|INTERACT|SLEEP|ALERT
    "last_event": "TOUCH_LEFT_TAP"  // 最近一次事件
}

GET  http://localhost:8000/api/events?limit=20
响应:
[
    "[1400] TOUCH_LEFT_TAP: expr=HAPPY, rgb=(0,255,50), state=ACTIVE",
    "[1395] NFC_CARD: expr=FOCUS, rgb=(50,50,255), state=INTERACT",
    ...
]

POST http://localhost:8000/api/command
请求体:
{
    "cmd": "set_expression",    // 命令类型
    "value": 2                   // 参数
}
```

### 3.5 UI 设计稿

```
┌──────────────────────────────────────────────────┐
│  🤖 桌面学术助手 - 控制面板           [🟢 已连接] │
├──────────────────────────────────────────────────┤
│                                                   │
│  ┌─────────────────┐  ┌──────────────────────┐   │
│  │                 │  │  状态: ACTIVE         │   │
│  │   (> ^_^ )>    │  │  情绪值: ████████░░ 0.72│  │
│  │                 │  │  表情: HAPPY           │   │
│  │   [表情预览区]   │  │  RGB:  (0, 255, 50)    │   │
│  │   160×160       │  │        🟢             │   │
│  │                 │  │  最近事件: 触摸-左-点击 │   │
│  └─────────────────┘  └──────────────────────┘   │
│                                                   │
│  ═══════════════ 手动控制 ═══════════════════    │
│                                                   │
│  表情:                                             │
│  [😐普通] [😊开心] [🧐专注] [😡生气]              │
│  [💤休眠] [😲惊讶] [😢难过] [💗爱心]              │
│                                                   │
│  灯光:                                             │
│  [🔴红] [🟢绿] [🔵蓝] [🟡黄] [🟣紫] [⚫关]     │
│  R: [━━━━━━━━━●────────] 128                       │
│  G: [━━━━━━━━━━━━━━●────] 200                       │
│  B: [━━━━━━━●──────────] 50                        │
│                                                   │
│  ═══════════════ 事件日志 ═══════════════════    │
│                                                   │
│  14:32:01  触摸-左-点击    → HAPPY  🟢(0,255,50) │
│  14:31:45  NFC 卡片 4A3F... → FOCUS 🔵(50,50,255)│
│  14:30:12  姿态-摇晃        → SURPRISE 🟠(255,128,0)│
│  14:25:00  系统启动          → NORMAL ⚪(0,0,0)   │
│                                                   │
└──────────────────────────────────────────────────┘
```

### 3.6 表情 ID 对照表

| ID | 名称 | 图标建议 | 描述 |
|----|------|----------|------|
| 0 | NORMAL | 😐 | 普通/默认，开机和待机 |
| 1 | HAPPY | 😊 | 开心，触摸响应 |
| 2 | FOCUS | 🧐 | 专注，NFC 学习卡 |
| 3 | ANGRY | 😡 | 生气，倾倒告警 |
| 4 | SLEEP | 💤 | 休眠，长时间无交互 |
| 5 | SURPRISE | 😲 | 惊讶，摇晃触发 |
| 6 | SAD | 😢 | 难过，情绪低落 |
| 7 | LOVE | 💗 | 爱心，双击触摸 |

### 3.7 前端开发指引

#### 基础框架 (index.html)

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>桌面学术助手 - 控制面板</title>
    <style>
        /* CSS 样式写这里，或外链 style.css */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background: #1a1a2e;
            color: #eee;
            display: flex;
            justify-content: center;
            padding: 20px;
        }
        .container {
            max-width: 700px;
            width: 100%;
            background: #16213e;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.4);
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .header h1 { font-size: 1.4em; }
        .status-dot {
            width: 12px; height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
        }
        .status-dot.connected { background: #4caf50; }
        .status-dot.disconnected { background: #f44336; }

        .main-panel {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }
        .preview-box {
            width: 160px; height: 160px;
            background: #000;
            border-radius: 12px;
            border: 2px solid #333;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 3em;
        }
        .info-box {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid #2a2a4a;
        }
        .emotion-bar {
            height: 8px;
            background: #333;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 4px;
        }
        .emotion-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }
        .section-title {
            font-size: 0.85em;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin: 16px 0 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid #2a2a4a;
        }
        .btn-group {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .btn {
            padding: 8px 14px;
            border: 1px solid #444;
            border-radius: 8px;
            background: #1a1a3e;
            color: #ddd;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.15s;
        }
        .btn:hover { background: #2a2a5e; border-color: #666; }
        .btn.active { background: #3a3a8e; border-color: #88f; }

        .color-slider {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 4px 0;
        }
        .color-slider label { width: 20px; font-weight: bold; }
        .color-slider input[type=range] { flex: 1; }
        .color-slider span { width: 30px; text-align: right; font-size: 0.85em; }

        .event-log {
            max-height: 200px;
            overflow-y: auto;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 0.8em;
            background: #0d1117;
            border-radius: 8px;
            padding: 10px;
        }
        .event-log .entry { padding: 4px 0; border-bottom: 1px solid #1a1a2e; }
        .event-log .time { color: #58a6ff; }
        .event-log .event-name { color: #ffa657; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 桌面学术助手</h1>
            <div>
                <span class="status-dot" id="status-dot"></span>
                <span id="status-text">检测中...</span>
            </div>
        </div>

        <div class="main-panel">
            <div class="preview-box" id="face-preview">😐</div>
            <div class="info-box">
                <div class="info-row"><span>系统状态</span><strong id="info-state">--</strong></div>
                <div class="info-row"><span>当前表情</span><strong id="info-expr">--</strong></div>
                <div class="info-row"><span>RGB 灯光</span><strong id="info-rgb">--</strong></div>
                <div>情绪值 <span id="info-emotion-val">--</span></div>
                <div class="emotion-bar">
                    <div class="emotion-fill" id="emotion-fill" style="width:50%"></div>
                </div>
                <div class="info-row"><span>最近事件</span><strong id="info-event">--</strong></div>
            </div>
        </div>

        <div class="section-title">🎭 表情控制</div>
        <div class="btn-group" id="expr-buttons">
            <button class="btn" data-expr="0">😐 普通</button>
            <button class="btn" data-expr="1">😊 开心</button>
            <button class="btn" data-expr="2">🧐 专注</button>
            <button class="btn" data-expr="3">😡 生气</button>
            <button class="btn" data-expr="4">💤 休眠</button>
            <button class="btn" data-expr="5">😲 惊讶</button>
            <button class="btn" data-expr="6">😢 难过</button>
            <button class="btn" data-expr="7">💗 爱心</button>
        </div>

        <div class="section-title">💡 灯光控制</div>
        <div class="color-slider">
            <label style="color:#ff5252">R</label>
            <input type="range" id="slider-r" min="0" max="255" value="0">
            <span id="val-r">0</span>
        </div>
        <div class="color-slider">
            <label style="color:#4caf50">G</label>
            <input type="range" id="slider-g" min="0" max="255" value="0">
            <span id="val-g">0</span>
        </div>
        <div class="color-slider">
            <label style="color:#448aff">B</label>
            <input type="range" id="slider-b" min="0" max="255" value="0">
            <span id="val-b">0</span>
        </div>
        <div class="btn-group" style="margin-top:8px">
            <button class="btn" id="btn-apply-rgb">应用灯光</button>
            <button class="btn" id="btn-off-rgb">关灯</button>
        </div>

        <div class="section-title">📋 事件日志</div>
        <div class="event-log" id="event-log">
            <div class="entry">等待连接...</div>
        </div>
    </div>

    <script>
        // JavaScript 逻辑写这里，或外链 app.js
        const API = 'http://localhost:8000';
        const EMOJI_MAP = ['😐', '😊', '🧐', '😡', '💤', '😲', '😢', '💗'];
        const EXPR_NAMES = ['NORMAL','HAPPY','FOCUS','ANGRY','SLEEP','SURPRISE','SAD','LOVE'];

        async function fetchStatus() {
            try {
                const res = await fetch(`${API}/api/status`);
                if (!res.ok) throw new Error('API error');
                const data = await res.json();

                document.getElementById('status-dot').className = 'status-dot connected';
                document.getElementById('status-text').textContent = '已连接';
                document.getElementById('face-preview').textContent = EMOJI_MAP[data.expression_id] || '🤖';
                document.getElementById('info-state').textContent = data.state;
                document.getElementById('info-expr').textContent = data.expression;
                document.getElementById('info-rgb').textContent = `(${data.rgb.join(',')})`;
                document.getElementById('info-event').textContent = data.last_event;
                document.getElementById('info-emotion-val').textContent = data.emotion.toFixed(2);

                const pct = (data.emotion * 100).toFixed(0) + '%';
                document.getElementById('emotion-fill').style.width = pct;

                // 高亮当前表情按钮
                document.querySelectorAll('#expr-buttons .btn').forEach(btn => {
                    btn.classList.toggle('active', parseInt(btn.dataset.expr) === data.expression_id);
                });

                // 更新滑块
                document.getElementById('slider-r').value = data.rgb[0];
                document.getElementById('slider-g').value = data.rgb[1];
                document.getElementById('slider-b').value = data.rgb[2];
                document.getElementById('val-r').textContent = data.rgb[0];
                document.getElementById('val-g').textContent = data.rgb[1];
                document.getElementById('val-b').textContent = data.rgb[2];

            } catch(e) {
                document.getElementById('status-dot').className = 'status-dot disconnected';
                document.getElementById('status-text').textContent = '未连接';
            }
        }

        async function fetchEvents() {
            try {
                const res = await fetch(`${API}/api/events?limit=20`);
                if (!res.ok) return;
                const events = await res.json();
                const logDiv = document.getElementById('event-log');
                logDiv.innerHTML = events.map(e => {
                    const match = e.match(/^\[(\d+)\]\s+(.+)$/);
                    if (match) {
                        return `<div class="entry"><span class="time">[${match[1]}]</span> <span class="event-name">${match[2]}</span></div>`;
                    }
                    return `<div class="entry">${e}</div>`;
                }).reverse().join('');
            } catch(e) {}
        }

        async function sendCommand(cmd, value) {
            try {
                await fetch(`${API}/api/command`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({cmd, value})
                });
            } catch(e) {
                console.error('Command failed:', e);
            }
        }

        // 表情按钮
        document.querySelectorAll('#expr-buttons .btn').forEach(btn => {
            btn.addEventListener('click', () => {
                sendCommand('set_expression', parseInt(btn.dataset.expr));
            });
        });

        // 灯光应用
        document.getElementById('btn-apply-rgb').addEventListener('click', () => {
            const r = +document.getElementById('slider-r').value;
            const g = +document.getElementById('slider-g').value;
            const b = +document.getElementById('slider-b').value;
            sendCommand('set_rgb', [r, g, b]);
        });

        document.getElementById('btn-off-rgb').addEventListener('click', () => {
            sendCommand('set_rgb', [0, 0, 0]);
            document.getElementById('slider-r').value = 0;
            document.getElementById('slider-g').value = 0;
            document.getElementById('slider-b').value = 0;
        });

        // 滑块实时更新数值
        ['r','g','b'].forEach(ch => {
            document.getElementById(`slider-${ch}`).addEventListener('input', function() {
                document.getElementById(`val-${ch}`).textContent = this.value;
            });
        });

        // 轮询
        setInterval(fetchStatus, 500);
        setInterval(fetchEvents, 2000);
        fetchStatus();
        fetchEvents();
    </script>
</body>
</html>
```

### 3.8 开发方法

**无需启动 B 的后端就可以独立开发：**

1. 先把上面 HTML 保存为 `pc_backend/web_ui/index.html`
2. 用浏览器直接打开 `index.html`（`file://` 协议）
3. 页面会显示"未连接"——这是正常的，因为没有 API 后端
4. 你的目标是：**把 HTML/CSS/JS 调好，等 B 的 API 就绪后替换 API 地址就能通**

**如果想更真实地调试**，可以写一个最小的 mock 服务器：

```python
# mock_server.py — 独立运行，不依赖任何人
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import random
import time

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class MockState:
    current_expression = None
    current_rgb = [0, 0, 0]
    last_event = "MOCK_STARTUP"
    event_log = [f"[{int(time.time())}] MOCK: 模拟事件"]
    fsm = None

    class current_expression_class:
        name = "HAPPY"
        def __int__(self): return 1
    current_expression = current_expression_class()

    class fsm_class:
        emotion_value = 0.65
        class state:
            name = "ACTIVE"
    fsm = fsm_class()

mock = MockState()

@app.get("/api/status")
def status():
    mock.fsm.emotion_value = max(0.1, min(0.9, mock.fsm.emotion_value + random.uniform(-0.05, 0.05)))
    return {
        "expression": mock.current_expression.name,
        "expression_id": int(mock.current_expression),
        "emotion": round(mock.fsm.emotion_value, 3),
        "rgb": mock.current_rgb,
        "state": mock.fsm.state.name,
        "last_event": mock.last_event,
    }

@app.get("/api/events")
def events(limit: int = 20):
    return mock.event_log[-limit:]

@app.post("/api/command")
def command(cmd: dict):
    mock.last_event = f"CMD: {cmd.get('cmd')}={cmd.get('value')}"
    mock.event_log.append(f"[{int(time.time())}] {mock.last_event}")
    return {"status": "ok"}

if __name__ == "__main__":
    print("Mock API running at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 四、接口规范

### 与 B (PC 后端)

| 项目 | 约定 |
|------|------|
| API 地址 | `http://localhost:8000` |
| 状态轮询 | `GET /api/status` 每 500ms |
| 事件日志 | `GET /api/events?limit=50` 每 2s |
| 命令下发 | `POST /api/command` body: `{"cmd":"set_expression","value":2}` |
| API 文档 | `http://localhost:8000/docs` (FastAPI 自动生成，可参考) |
| 实时推送 | 后续加 WebSocket，轮询先跑通 |

### 与 A (固件)

| 项目 | 约定 |
|------|------|
| NFC 接线 | 7 根杜邦线，按 2.1 节表格连接 |
| 接线验证 | 配合 A 烧录 NFC 固件，SSCOM 观察 `card=1` |

### 与 E (文档/演示)

| 项目 | 约定 |
|------|------|
| 接线照片 | 接线完毕后拍照（每根线清晰可见），发给 E |
| UI 截图 | Web 面板完成后截图，发给 E |
| 操作演示 | 配合 E 录制"打开面板→控制机器人"的操作流程 |

---

## 五、完成标准

- [ ] RC522 模块 7 根杜邦线正确连接到 STM32 开发板
- [ ] 配合 A 验证接线：SSCOM 显示 `[NFC DBG] poll: card=1`
- [ ] 备线完成，接线照片已拍
- [ ] `web_ui/index.html` 能独立在浏览器中打开，布局完整
- [ ] 表情按钮点击有高亮反馈
- [ ] RGB 滑块拖动有数值更新
- [ ] 接上 B 的 API 后（或 mock 服务器），状态面板能实时刷新
- [ ] 接上 B 的 API 后（或 mock 服务器），事件日志能正确显示
- [ ] 与 B 确认 POST /api/command 的请求格式
