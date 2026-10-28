"""Turns memory hits into a context block for the Brain."""
from __future__ import annotations

from dataclasses import dataclass, field

from .store import Memory, MemoryStore

_HEADER = ("Relevant memory (may be outdated or wrong: verify paths, permissions and current state "
           "before relying on any of it):")


@dataclass
class ContextPack:
    items: list = field(default_factory=list)   # list[Memory]
    text: str = ""

    @property
    def empty(self) -> bool:
        return not self.items

    @property
    def private(self) -> bool:
        return any(m.kind in ("preference", "project", "conversation") for m in self.items)


class Retriever:
    def __init__(self, store: MemoryStore):
        self.store = store

    def context_for(self, text: str, kinds=None, limit: int = 6) -> ContextPack:
        hits = self.store.search(text, kinds=kinds, limit=limit)
        if not hits:
            return ContextPack()
        self.store.mark_used([h.memory.id for h in hits])
        lines = [_HEADER]
        for h in hits:
            m: Memory = h.memory
            flag = " STALE" if m.stale else ""
            lines.append(f"- [{m.kind}#{m.id} conf={m.confidence:.1f}{flag}] {m.key}: {m.content}")
        return ContextPack([h.memory for h in hits], "\n".join(lines))
