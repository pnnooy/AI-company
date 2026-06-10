"""
llm_client.py - LLM client (multi-backend)
==========================================
Supports DeepSeek / Anthropic / OpenAI-compatible backends, auto-detect.

Config (any one):
    $env:DEEPSEEK_API_KEY = "sk-..."      # DeepSeek (recommended, cheapest)
    $env:ANTHROPIC_API_KEY = "sk-ant-..." # Anthropic Claude
    $env:OPENAI_API_KEY = "sk-..."        # OpenAI / compatible API
    $env:OPENAI_BASE_URL = "https://..."  # Custom API base URL (optional)

Models (auto-selected per backend):
    DeepSeek   -> deepseek-chat
    Anthropic  -> claude-haiku-4-5-20251001
    OpenAI     -> gpt-4o-mini
"""

import json
import logging
import os
import queue
import threading
import time
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)

# ============================================================================
# Backend auto-detection
# ============================================================================

def _detect_backend() -> tuple:
    # SJTU (free, priority)
    key = os.environ.get("SJTU_API_KEY", "")
    if key:
        return "sjtu", key, "https://models.sjtu.edu.cn/api/v1"

    # DeepSeek
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return "deepseek", key, "https://api.deepseek.com"

    # Anthropic
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return "anthropic", key, None

    # OpenAI / compatible
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        base = os.environ.get("OPENAI_BASE_URL", None)
        return "openai", key, base

    return "none", "", None


BACKEND, API_KEY, BASE_URL = _detect_backend()

DEFAULT_MODELS = {
    "sjtu": "deepseek-chat",      # Free SJTU: deepseek-chat / glm / qwen / minimax
    "deepseek": "deepseek-chat",
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}

LLM_MODEL = os.environ.get("LLM_MODEL", DEFAULT_MODELS.get(BACKEND, "deepseek-chat"))
LLM_MAX_TOKENS = 150
LLM_TEMPERATURE = 0.9
LLM_REFLECT_COOLDOWN_SEC = 15   # 反思低优先级，降频
LLM_EVENT_COOLDOWN_SEC = 8       # 事件反应
LLM_CHAT_COOLDOWN_SEC = 0        # 聊天无冷却，即时响应
LLM_TIMEOUT_SEC = 10             # API 超时
LLM_BACKOFF_BASE_SEC = 15        # 429 退避基础时间
LLM_BACKOFF_MAX_SEC = 120        # 最大退避时间

VALID_EXPRESSIONS = {"normal", "happy", "focus", "angry", "sleep", "surprise", "sad", "love"}


# ============================================================================
# LLM Client
# ============================================================================

class LLMClient:
    """Multi-backend LLM client, background thread, async calls"""

    def __init__(self, backend: str = "", api_key: str = "", base_url: str = ""):
        self.backend = backend or BACKEND
        self.api_key = api_key or API_KEY
        self.base_url = base_url or BASE_URL
        self.model = LLM_MODEL
        self._client = None

        self._request_queue = queue.PriorityQueue()  # (priority, seq, request)
        self._request_seq = 0
        self._result_queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_call_time = 0.0

        self.call_count = 0
        self.error_count = 0
        self._backoff_until = 0.0     # 退避截止时间
        self._backoff_sec = 0.0        # 当前退避秒数

        self.last_thought: str = ""
        self.last_emotion_delta: float = 0.0
        self.last_suggested_expr: str = ""
        self.last_reply: str = ""

        self.on_reply: Optional[Callable[[str, float, str], None]] = None

    @property
    def available(self) -> bool:
        return self.backend != "none" and len(self.api_key) > 8

    def start(self):
        if not self.available:
            logger.info("LLM not configured (set DEEPSEEK_API_KEY or ANTHROPIC_API_KEY)")
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        logger.info("LLM started: %s / %s", self.backend, self.model)

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _in_backoff(self) -> bool:
        """检查是否在退避期"""
        if time.time() < self._backoff_until:
            return True
        return False

    def reflect(self, state, emotion, expression, user_present, events):
        if not self.available or not self._running:
            return
        if self._in_backoff():
            return
        self._request_seq += 1
        self._request_queue.put((2, self._request_seq, {
            "type": "reflect", "state": state, "emotion": emotion,
            "expression": expression, "user_present": user_present,
            "events": events[-8:],
        }))

    def react(self, trigger, state, emotion, expression, user_present, events):
        if not self.available or not self._running:
            return
        if self._in_backoff():
            return
        now = time.time()
        if now - self._last_call_time < LLM_EVENT_COOLDOWN_SEC:
            return
        self._last_call_time = now
        self._request_seq += 1
        self._request_queue.put((2, self._request_seq, {
            "type": "react", "trigger": trigger,
            "state": state, "emotion": emotion,
            "expression": expression, "user_present": user_present,
            "events": events[-8:],
        }))

    def chat(self, user_message, state, emotion, expression, user_present, events):
        if not self.available or not self._running:
            return
        if self._in_backoff():
            return
        self._request_seq += 1
        # 聊天高优先级：priority=1，即时响应
        self._request_queue.put((1, self._request_seq, {
            "type": "chat", "user_message": user_message,
            "state": state, "emotion": emotion,
            "expression": expression, "user_present": user_present,
            "events": events[-8:],
        }))

    def get_result(self) -> Optional[Dict[str, Any]]:
        try:
            return self._result_queue.get_nowait()
        except queue.Empty:
            return None

    def _worker(self):
        self._init_client()
        if self._client is None:
            return
        while self._running:
            try:
                _, _, req = self._request_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                result = self._call_api(req)
                if result:
                    self._result_queue.put(result)
                    self.call_count += 1
                    # 成功后重置退避
                    self._backoff_sec = 0
                    if result.get("type") == "chat" and self.on_reply:
                        self.on_reply(result.get("reply", ""),
                                      result.get("emotion_delta", 0.0),
                                      result.get("expression", "normal"))
            except Exception as e:
                self.error_count += 1
                err_str = str(e)
                if "429" in err_str:
                    # 速率限制：指数退避
                    self._backoff_sec = max(self._backoff_sec * 2, LLM_BACKOFF_BASE_SEC)
                    self._backoff_sec = min(self._backoff_sec, LLM_BACKOFF_MAX_SEC)
                    self._backoff_until = time.time() + self._backoff_sec
                    logger.warning("LLM rate limited, backing off %ds", self._backoff_sec)
                else:
                    logger.error("LLM call failed: %s", err_str[:100])

    def _init_client(self):
        if self.backend in ("sjtu", "deepseek", "openai"):
            try:
                from openai import OpenAI
                import httpx
                timeout = httpx.Timeout(LLM_TIMEOUT_SEC, connect=5.0)
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=timeout,
                    max_retries=1,  # 快速失败，不做长时间重试
                )
                if not self.model:
                    self.model = DEFAULT_MODELS.get(self.backend, "deepseek-chat")
            except ImportError:
                logger.error("openai not installed: pip install openai")
        elif self.backend == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.error("anthropic not installed: pip install anthropic")

    def _call_api(self, req: dict) -> Optional[dict]:
        from .character import build_context

        inst_key = req["type"]
        if req["type"] == "react":
            inst_key = "react"
        prompt = build_context(
            state=req["state"], emotion=req["emotion"],
            expression=req["expression"], user_present=req["user_present"],
            recent_events=req["events"],
            instruction_key=inst_key,
            user_message=req.get("user_message", ""),
            trigger=req.get("trigger", ""),
        )

        if self.backend in ("sjtu", "deepseek", "openai"):
            return self._call_openai(prompt, req["type"])
        elif self.backend == "anthropic":
            return self._call_anthropic(prompt)
        return None

    def _call_openai(self, prompt: str, req_type: str) -> Optional[dict]:
        try:
            response = self._client.chat.completions.create(
                model=self.model, max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
                messages=[
                    {"role": "system", "content": "Reply in JSON format only. No other text."},
                    {"role": "user", "content": prompt},
                ],
            )
            text = response.choices[0].message.content.strip()
            result = self._parse_json(text)
            result["type"] = req_type
            self._save_result(result, req_type)
            return result
        except Exception as e:
            err_type = type(e).__name__
            logger.debug("LLM API error (%s): %s", err_type, str(e)[:100])
            raise

    def _call_anthropic(self, prompt: str) -> Optional[dict]:
        response = self._client.messages.create(
            model=self.model, max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
            system="Reply in JSON format only. No other text.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        return self._parse_json(text)

    def _save_result(self, result: dict, req_type: str):
        if req_type in ("reflect", "react"):
            self.last_thought = result.get("thought", "")
            self.last_emotion_delta = result.get("emotion_delta", 0.0)
            self.last_suggested_expr = result.get("expression", "")
            logger.info("PiPi: %s", self.last_thought)
        elif req_type == "chat":
            self.last_reply = result.get("reply", "")
            logger.info("PiPi: %s", self.last_reply)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract JSON from LLM output (handles multiple formats)"""
        import re
        text = text.strip()

        # Remove markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1])
            else:
                text = "\n".join(lines[1:])

        # Try direct parse
        try:
            return LLMClient._validate(json.loads(text))
        except (json.JSONDecodeError, ValueError):
            pass

        # Extract {...} block (supports nesting)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        raw = match.group() if match else text

        # Standard JSON
        try:
            return LLMClient._validate(json.loads(raw))
        except (json.JSONDecodeError, ValueError):
            pass

        # Single quotes -> double quotes
        try:
            fixed = re.sub(r"'(thought|reply|emotion_delta|expression)'", r'"\1"', raw)
            fixed = re.sub(r"(?<!\\)'([^']*)'", r'"\1"', fixed)
            return LLMClient._validate(json.loads(fixed))
        except (json.JSONDecodeError, ValueError):
            pass

        # Python dict format (ast.literal_eval)
        try:
            import ast
            data = ast.literal_eval(raw)
            if isinstance(data, dict):
                return LLMClient._validate(data)
        except (ValueError, SyntaxError):
            pass

        logger.debug("LLM JSON parse failed: %s", text[:120])
        return {"thought": "", "reply": "", "emotion_delta": 0.0, "expression": "normal"}

    @staticmethod
    def _validate(data: dict) -> dict:
        """Validate and normalize LLM output"""
        expr = data.get("expression", "normal")
        if expr not in VALID_EXPRESSIONS:
            data["expression"] = "normal"
        delta = data.get("emotion_delta", 0.0)
        data["emotion_delta"] = max(-0.1, min(0.1, float(delta)))
        return data
