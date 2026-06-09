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

    def __init__(self, link: UartLink, fsm: MachineState):
        self.link = link
        self.fsm = fsm
        self._server_thread: Optional[threading.Thread] = None
        self._app = None

    def start(self, host: str = "0.0.0.0", port: int = 5000):
        """启动 API 服务（后台线程）"""
        try:
            from flask import Flask, jsonify, request
        except ImportError:
            logger.error("Flask 未安装，无法启动 Web API。运行: pip install flask")
            return

        app = Flask(__name__)
        link = self.link
        fsm = self.fsm

        # ── 端点定义 ──────────────────────────

        @app.route("/api/health")
        def health():
            return jsonify({"status": "ok"})

        @app.route("/api/status")
        def status():
            """获取机器人当前状态"""
            return jsonify({
                "state": fsm.state.name,
                "emotion": round(fsm.emotion_value, 3),
                "expression": None,  # TODO: 从设备查询
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

        @app.route("/api/stats")
        def stats():
            """获取通信统计"""
            return jsonify(link.get_stats())

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
