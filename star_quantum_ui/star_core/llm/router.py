"""Model Router: local first, optional cloud fallback, and JSON replies that are validated and repaired."""
from __future__ import annotations

import json
import re
from typing import Callable

from ..config import Config
from .base import ChatResponse, LLMClient, LLMError


def extract_json(text: str) -> dict:
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    start = t.find("{")
    if start < 0:
        raise ValueError("no JSON object found in the reply")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        c = t[i]
        if in_str:
            esc = (not esc) if c == "\\" else False
            if c == '"' and not esc:
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                raw = t[start:i + 1]
                try:
                    return json.loads(raw, strict=False)
                except json.JSONDecodeError:
                    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
                    return json.loads(cleaned, strict=False)
    # If trailing close braces were missing due to token cut-off, attempt recovery
    if depth > 0:
        candidate = t[start:]
        if in_str:
            candidate += '"'
        candidate += "}" * depth
        try:
            return json.loads(candidate, strict=False)
        except Exception:
            pass
    raise ValueError("unbalanced JSON in the reply")


class ModelRouter:
    def __init__(self, local: LLMClient | None, cloud: LLMClient | None, config: Config,
                 on_call: Callable[[ChatResponse], None] | None = None):
        self.local, self.cloud, self.config, self.on_call = local, cloud, config, on_call
        self.last: ChatResponse | None = None

    def _order(self, task: str, cloud_ok: bool) -> list[LLMClient]:
        order: list[LLMClient] = []
        cloud_allowed = cloud_ok and self.cloud is not None and self.cloud.available()
        if cloud_allowed and task in self.config.cloud_tasks:
            order.append(self.cloud)
        if self.local is not None and self.local.available():
            order.append(self.local)
        if cloud_allowed and self.config.cloud_fallback and self.cloud not in order:
            order.append(self.cloud)
        return order

    def chat(self, messages: list[dict], *, task: str = "general", json_mode: bool = False,
             cloud_ok: bool = True, temperature: float = 0.1) -> ChatResponse:
        errors = []
        order = self._order(task, cloud_ok)
        if not order:
            raise LLMError("no language model available (start Ollama, or enable cloud fallback with an API key)")
        for client in order:
            try:
                resp = client.chat(messages, json_mode=json_mode, temperature=temperature, task=task)
                self.last = resp
                if self.on_call:
                    self.on_call(resp)
                return resp
            except LLMError as e:
                errors.append(str(e))
        raise LLMError("; ".join(errors))

    def json_chat(self, messages: list[dict], *, task: str, required: list[str] | tuple = (),
                  check: Callable[[dict], str | None] | None = None, retries: int = 2,
                  cloud_ok: bool = True) -> dict:
        msgs = list(messages)
        last_err = "unknown"
        for _ in range(retries + 1):
            resp = self.chat(msgs, task=task, json_mode=True, cloud_ok=cloud_ok)
            try:
                data = extract_json(resp.text)
                missing = [k for k in required if k not in data]
                if missing:
                    raise ValueError(f"missing keys: {', '.join(missing)}")
                problem = check(data) if check else None
                if problem:
                    raise ValueError(problem)
                return data
            except (ValueError, json.JSONDecodeError) as e:
                last_err = str(e)
                msgs = msgs + [{"role": "assistant", "content": resp.text},
                               {"role": "user", "content": f"That reply was rejected: {last_err}. "
                                                           "Reply again with ONLY one valid JSON object that fixes this."}]
        raise LLMError(f"model did not return usable JSON ({last_err})")
