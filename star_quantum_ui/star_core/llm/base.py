from __future__ import annotations

from dataclasses import dataclass


class LLMError(Exception):
    pass


@dataclass
class ChatResponse:
    text: str
    model: str = ""
    provider: str = ""
    tokens: int = 0
    seconds: float = 0.0


class LLMClient:
    name = "llm"

    def available(self) -> bool:
        return True

    def chat(self, messages: list[dict], *, json_mode: bool = False, temperature: float = 0.1,
             timeout: float = 180) -> ChatResponse:  # pragma: no cover - interface
        raise NotImplementedError
