"""Local models through Ollama's HTTP API (standard library only)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .base import ChatResponse, LLMClient, LLMError


class OllamaClient(LLMClient):
    name = "ollama"

    def __init__(self, url: str = "http://127.0.0.1:11434", model: str = "qwen2.5:7b-instruct"):
        self.url, self.model = url.rstrip("/"), model
        self._ok_until = 0.0
        self._ok = False

    def available(self) -> bool:
        now = time.time()
        if now < self._ok_until:
            return self._ok
        try:
            with urllib.request.urlopen(self.url + "/api/tags", timeout=5) as r:
                names = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
            self._ok = any(n == self.model or n.split(":")[0] == self.model.split(":")[0] for n in names) or not names
            self._ok_until = now + 15
        except Exception:
            self._ok = False
            self._ok_until = now + 2
        return self._ok

    def chat(self, messages, *, json_mode=False, temperature=0.1, timeout=180, task="general", max_tokens=None) -> ChatResponse:
        if max_tokens is None:
            if task in ("planning", "replan"):
                max_tokens = 1024
            elif json_mode:
                max_tokens = 350
            else:
                max_tokens = 512
        num_ctx = 4096 if task in ("planning", "replan") else 2048
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "keep_alive": "60m",
                   "options": {
                       "temperature": temperature,
                       "num_ctx": num_ctx,
                       "num_predict": max_tokens,
                   }}
        if json_mode:
            payload["format"] = "json"
        req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            return ChatResponse(data["message"]["content"], self.model, self.name,
                                int(data.get("eval_count", 0)), time.time() - t0)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, OSError) as e:
            raise LLMError(f"ollama: {e}") from e
