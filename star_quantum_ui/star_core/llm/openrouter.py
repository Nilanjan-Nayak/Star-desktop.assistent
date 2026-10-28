"""Cloud models through OpenRouter (needs an API key). Standard library only."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .base import ChatResponse, LLMClient, LLMError


class OpenRouterClient(LLMClient):
    name = "openrouter"
    URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "openrouter/auto"):
        self.api_key, self.model = api_key, model

    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages, *, json_mode=False, temperature=0.1, timeout=180, **kwargs) -> ChatResponse:
        if not self.api_key:
            raise LLMError("openrouter: no API key configured")
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(self.URL, data=json.dumps(payload).encode("utf-8"), headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}", "X-Title": "STAR"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            return ChatResponse(data["choices"][0]["message"]["content"], data.get("model", self.model), self.name,
                                int(data.get("usage", {}).get("completion_tokens", 0)), time.time() - t0)
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, OSError) as e:
            raise LLMError(f"openrouter: {e}") from e
