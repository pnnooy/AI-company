"""
web_api.py — REST API 服务
=========================
为 Web 前端（C 角色）提供 HTTP API，查询机器人状态和发送指令。

更新日期: 2026-06-04

端点:
    GET  /api/status        → 机器人当前状态
    POST /api/expression    → 设置表情
    POST /api/led           → 设置 RGB 灯光
    GET  /api/stats         → 通信统计
    GET  /api/health        → 健康检查

Usage:
    from web_api import WebAPI
    api = WebAPI(link, fsm)
    api.start(host="0.0.0.0", port=5000)
"""

import logging
import threading
from typing import Optional

from comm.uart_link import UartLink
from comm.protocol import Cmd, Expression
from ai_engine.state_machine import MachineState

logger = logging.getLogger(__name__)


class WebAPI:
    """Web API 服务（后台线程）"""

    def __init__(self, link: UartLink, fsm: MachineState, llm_client=None):
        self.link = link
        self.fsm = fsm
        self.llm_client = llm_client
        self._server_thread: Optional[threading.Thread] = None
        self._app = None

    def start(self, host: str = "0.0.0.0", port: int = 5000):
        """启动 API 服务（后台线程）"""
        try:
            from flask import Flask, jsonify, request, render_template, send_file, Response
        except ImportError:
            logger.error("Flask 未安装，无法启动 Web API。运行: pip install flask")
            return

        import os
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
        link = self.link
        fsm = self.fsm
        llm_client = self.llm_client

        # ── 端点定义 ──────────────────────────

        @app.route("/api/health")
        def health():
            return jsonify({"status": "ok"})

        @app.route("/api/status")
        def status():
            import sys
            main_mod = sys.modules.get('__main__')
            expr = getattr(main_mod, 'current_expression', 'normal') or 'normal' if main_mod else 'normal'
            rgb = getattr(main_mod, 'last_rgb', [0, 0, 0]) or [0, 0, 0] if main_mod else [0, 0, 0]
            return jsonify({
                "state": fsm.state.name,
                "emotion": round(fsm.emotion_value, 3),
                "expression": expr,
                "rgb": list(rgb) if rgb else [0, 0, 0],
            })

        @app.route("/api/expression", methods=["POST"])
        def set_expression():
            """设置表情: {"expression": "HAPPY"}"""
            data = request.get_json()
            if not data or "expression" not in data:
                return jsonify({"error": "missing 'expression' field"}), 400

            expr_name = data["expression"].upper()
            try:
                expr = Expression[expr_name]
            except KeyError:
                return jsonify({
                    "error": f"unknown expression '{expr_name}'",
                    "valid": [e.name for e in Expression]
                }), 400

            ok = link.send_command(Cmd.SET_EXPR, bytes([int(expr)]))
            return jsonify({"ok": ok, "expression": expr_name})

        @app.route("/api/led", methods=["POST"])
        def set_led():
            """设置 RGB 灯光: {"r": 255, "g": 0, "b": 0}"""
            data = request.get_json()
            if not data or not all(k in data for k in ("r", "g", "b")):
                return jsonify({"error": "missing 'r', 'g', 'b' fields"}), 400

            r = max(0, min(255, int(data["r"])))
            g = max(0, min(255, int(data["g"])))
            b = max(0, min(255, int(data["b"])))

            ok = link.send_command(Cmd.SET_RGB, bytes([r, g, b]))
            return jsonify({"ok": ok, "rgb": (r, g, b)})

        @app.route("/")
        def index_page():
            """前端仪表盘"""
            return render_template("index.html")

        @app.route("/api/camera_frame")
        def camera_frame():
            import sys
            main_mod = sys.modules.get('__main__')
            jpg = getattr(main_mod, 'camera_jpeg', None) if main_mod else None
            if jpg:
                return Response(jpg, mimetype='image/jpeg')
            return jsonify({"error": "waiting for camera..."}), 404

        @app.route("/api/debug/event", methods=["POST"])
        def debug_event():
            data = request.get_json()
            if not data:
                return jsonify({"error": "no data"}), 400
            evt = data.get("event", "")
            if evt == "touch":
                fsm.on_touch_event(int(__import__('time').time() * 1000))
            elif evt == "nfc":
                from comm.protocol import NFCLevel
                lvl = NFCLevel(data.get("level", 1))
                boost = 0.3 if lvl.value >= 1 else 0.1
                fsm.on_nfc_event(int(__import__('time').time() * 1000), boost)
            return jsonify({"ok": True, "event": evt})

        @app.route("/api/stats")
        def stats():
            return jsonify(link.get_stats())

        @app.route("/api/chat", methods=["POST"])
        def chat():
            data = request.get_json()
            if not data or "message" not in data:
                return jsonify({"error": "missing 'message' field"}), 400
            user_msg = data["message"].strip()
            if not user_msg:
                return jsonify({"error": "empty message"}), 400
            if llm_client and llm_client.available:
                import sys
                main_mod = sys.modules.get('__main__')
                events = getattr(main_mod, '_event_history', [])[-8:] if main_mod else []
                llm_client.chat(
                    user_message=user_msg, state=fsm.state.name,
                    emotion=fsm.emotion_value, expression="normal",
                    user_present=True, events=events,
                )
                return jsonify({"ok": True, "message": user_msg,
                                "note": "LLM is thinking..."})
            else:
                return jsonify({"ok": False, "error": "LLM not available",
                                "hint": "Set SJTU_API_KEY"}), 503

        @app.route("/api/last_thought")
        def last_thought():
            if llm_client:
                return jsonify({
                    "thought": llm_client.last_thought,
                    "reply": llm_client.last_reply,
                    "emotion_delta": llm_client.last_emotion_delta,
                    "expression": llm_client.last_suggested_expr,
                    "calls": llm_client.call_count, "errors": llm_client.error_count,
                })
            return jsonify({"thought": "", "reply": "", "error": "LLM not available"})

        # 静态文件（前端页面）
        @app.route("/")
        def index():
            return jsonify({
                "name": "Desktop Academic Assistant",
                "version": "2.0",
                "endpoints": [
                    "GET  /api/status",
                    "POST /api/expression",
                    "POST /api/led",
                    "GET  /api/stats",
                    "GET  /api/health",
                ]
            })

        self._app = app
        self._server_thread = threading.Thread(
            target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
            daemon=True
        )
        self._server_thread.start()
        logger.info(f"Web API 服务已启动: http://{host}:{port}")

    def stop(self):
        """停止服务"""
        # Flask 开发服务器没有优雅停止的 API，线程是 daemon 的会自动退出
        logger.info("Web API 服务已停止（daemon 线程自动退出）")
