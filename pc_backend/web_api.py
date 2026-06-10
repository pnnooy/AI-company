"""
web_api.py - REST API service + Dashboard
=========================================
Provides HTTP API for the frontend and serves the dashboard.

Endpoints:
    GET  /                     -> dashboard page
    GET  /api/status           -> robot state
    POST /api/expression       -> set expression
    POST /api/led              -> set RGB LED
    POST /api/chat             -> send chat message
    GET  /api/last_thought     -> LLM thoughts & replies
    GET  /api/camera_frame     -> latest camera JPEG
    GET  /api/stats            -> serial stats
    POST /api/debug/event      -> simulate touch/NFC
    POST /api/debug/emotion    -> force emotion value
    GET  /api/health           -> health check
"""

import logging
import threading
from typing import Optional

from comm.uart_link import UartLink
from comm.protocol import Cmd, Expression
from ai_engine.state_machine import MachineState

logger = logging.getLogger(__name__)


class WebAPI:
    """Web API service (background thread)"""

    def __init__(self, link: UartLink, fsm: MachineState, llm_client=None):
        self.link = link
        self.fsm = fsm
        self.llm_client = llm_client
        self._server_thread: Optional[threading.Thread] = None
        self._app = None

    def start(self, host: str = "0.0.0.0", port: int = 5000):
        try:
            from flask import Flask, jsonify, request, render_template, Response
        except ImportError:
            logger.error("Flask not installed: pip install flask")
            return

        import os, sys, time
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
        link = self.link
        fsm = self.fsm
        llm_client = self.llm_client

        def _get_main():
            return sys.modules.get('__main__')

        # --- Dashboard ---
        @app.route("/")
        def index_page():
            return render_template("index.html")

        # --- Status ---
        @app.route("/api/status")
        def status():
            m = _get_main()
            expr = getattr(m, 'current_expression', 'normal') or 'normal' if m else 'normal'
            rgb = getattr(m, 'last_rgb', [0, 0, 0]) or [0, 0, 0] if m else [0, 0, 0]
            ue = getattr(m, 'cached_user_emotion', 'neutral') or 'neutral' if m else 'neutral'
            uc = getattr(m, 'cached_emotion_conf', 0.0) or 0.0 if m else 0.0
            return jsonify({
                "state": fsm.state.name,
                "emotion": round(fsm.emotion_value, 3),
                "expression": expr,
                "rgb": list(rgb) if rgb else [0, 0, 0],
                "user_emotion": ue,
                "user_emotion_conf": round(uc, 2),
            })

        @app.route("/api/health")
        def health():
            return jsonify({"status": "ok"})

        # --- Commands ---
        @app.route("/api/expression", methods=["POST"])
        def set_expression():
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
            data = request.get_json()
            if not data or not all(k in data for k in ("r", "g", "b")):
                return jsonify({"error": "missing 'r', 'g', 'b' fields"}), 400
            r = max(0, min(255, int(data["r"])))
            g = max(0, min(255, int(data["g"])))
            b = max(0, min(255, int(data["b"])))
            ok = link.send_command(Cmd.SET_RGB, bytes([r, g, b]))
            return jsonify({"ok": ok, "rgb": (r, g, b)})

        # --- Camera ---
        @app.route("/api/camera_frame")
        def camera_frame():
            jpg = getattr(_get_main(), 'camera_jpeg', None)
            if jpg:
                return Response(jpg, mimetype='image/jpeg')
            return jsonify({"error": "waiting for camera..."}), 404

        # --- Chat ---
        @app.route("/api/chat", methods=["POST"])
        def chat():
            data = request.get_json()
            if not data or "message" not in data:
                return jsonify({"error": "missing 'message' field"}), 400
            user_msg = data["message"].strip()
            if not user_msg:
                return jsonify({"error": "empty message"}), 400
            if llm_client and llm_client.available:
                m = _get_main()
                events = getattr(m, '_event_history', [])[-8:] if m else []
                llm_client.chat(
                    user_message=user_msg, state=fsm.state.name,
                    emotion=fsm.emotion_value, expression="normal",
                    user_present=True, events=events,
                )
                return jsonify({"ok": True, "message": user_msg,
                                "note": "LLM is thinking..."})
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

        @app.route("/api/stats")
        def stats():
            return jsonify(link.get_stats())

        # --- Debug ---
        @app.route("/api/debug/emotion", methods=["POST"])
        def debug_emotion():
            data = request.get_json()
            if data and "emotion" in data:
                val = max(0.0, min(1.0, float(data["emotion"])))
                fsm.emotion_value = val
                fsm.last_event_time = int(time.time() * 1000)
                from ai_engine.rules import decide_by_emotion
                expr, rgb = decide_by_emotion(val)
                expr_name = expr.name.lower()
                link.send_command(Cmd.SET_EXPR, bytes([int(expr)]))
                link.send_command(Cmd.SET_RGB, bytes(rgb))
                m = _get_main()
                if m:
                    m.current_expression = expr_name
                    m.last_rgb = list(rgb)
                logger.info("Debug: emotion=%.2f expr=%s rgb=%s", val, expr_name, rgb)
                return jsonify({"ok": True, "emotion": val, "expression": expr_name, "rgb": rgb})
            return jsonify({"error": "missing emotion"}), 400

        @app.route("/api/debug/event", methods=["POST"])
        def debug_event():
            data = request.get_json()
            if not data:
                return jsonify({"error": "no data"}), 400
            evt = data.get("event", "")
            if evt == "touch":
                fsm.on_touch_event(int(time.time() * 1000))
            elif evt == "nfc":
                from comm.protocol import NFCLevel
                lvl = NFCLevel(data.get("level", 1))
                boost = 0.3 if lvl.value >= 1 else 0.1
                fsm.on_nfc_event(int(time.time() * 1000), boost)
            return jsonify({"ok": True, "event": evt})

        # --- Start ---
        self._app = app
        self._server_thread = threading.Thread(
            target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
            daemon=True
        )
        self._server_thread.start()
        logger.info("Web API started: http://%s:%s", host, port)

    def stop(self):
        logger.info("Web API stopped (daemon thread exits)")
