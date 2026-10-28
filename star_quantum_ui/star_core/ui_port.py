"""UIPort: everything the backend needs from a frontend, with no Qt in sight.

The same orchestrator runs against the real STAR window (BridgePort), a console, or a
recording stub in tests. Methods may be called from a worker thread.
"""
from __future__ import annotations

import itertools
import threading
from typing import Any, Protocol


class UIPort(Protocol):
    def set_state(self, state: str) -> None: ...
    def say(self, text: str) -> None: ...
    def open_tab(self, kind: str, title: str, payload: dict) -> str: ...
    def tab_event(self, tab_id: str, event: str, data: Any = None) -> None: ...
    def close_tab(self, tab_id: str) -> None: ...
    def metric(self, name: str, value: float) -> None: ...
    def ask(self, question: str, timeout: float | None = None) -> str | None: ...
    approval_tab_id: str | None
    def request_approval(self, title: str, description: str, info: dict, steps: list[str],
                         timeout: float | None = None, keep_open: bool = False) -> bool: ...
    def cancelled(self) -> bool: ...


class RecordingPort:
    """Test/headless port: records every call; approvals and answers are scripted."""

    def __init__(self, approvals: list[bool] | None = None, answers: list[str] | None = None,
                 default_approval: bool = True):
        self.calls: list[tuple] = []
        self.approvals = list(approvals or [])
        self.answers = list(answers or [])
        self.default_approval = default_approval
        self.cancel = threading.Event()
        self._ids = itertools.count(1)
        self.messages: list[str] = []
        self.approval_tab_id: str | None = None

    def _rec(self, *a):
        self.calls.append(a)

    def set_state(self, state): self._rec("state", state)

    def say(self, text):
        self.messages.append(text)
        self._rec("say", text)

    def open_tab(self, kind, title, payload):
        tid = f"{kind}-{next(self._ids)}"
        self._rec("open_tab", tid, kind, title, payload)
        return tid

    def tab_event(self, tab_id, event, data=None): self._rec("tab_event", tab_id, event, data)
    def close_tab(self, tab_id): self._rec("close_tab", tab_id)
    def metric(self, name, value): self._rec("metric", name, value)

    def ask(self, question, timeout=None):
        self._rec("ask", question)
        return self.answers.pop(0) if self.answers else None

    def request_approval(self, title, description, info, steps, timeout=None, keep_open=False):
        self._rec("approval", title, description, info, steps)
        ok = self.approvals.pop(0) if self.approvals else self.default_approval
        self.approval_tab_id = f"system-{next(self._ids)}" if (ok and keep_open) else None
        return ok

    def cancelled(self) -> bool:
        return self.cancel.is_set()

    # helpers for assertions
    def events(self, name: str) -> list[tuple]:
        return [c for c in self.calls if c[0] == name]

    def tab_events(self, event: str) -> list[tuple]:
        return [c for c in self.calls if c[0] == "tab_event" and c[2] == event]


class ConsolePort(RecordingPort):
    """Prints to the terminal and asks on stdin. Handy for `python -m star_core.cli`."""

    def say(self, text):
        super().say(text)
        print(f"STAR: {text}")

    def ask(self, question, timeout=None):
        print(f"STAR ?: {question}")
        try:
            return input("you> ").strip() or None
        except EOFError:
            return None

    def request_approval(self, title, description, info, steps, timeout=None, keep_open=False):
        print(f"\n== Approval needed: {title}\n{description}")
        for k, v in info.items():
            print(f"   {k}: {v}")
        for i, s in enumerate(steps, 1):
            print(f"   {i}. {s}")
        return input("approve? [y/N] ").strip().lower() in ("y", "yes", "h", "ha", "হ্যাঁ")

    def tab_event(self, tab_id, event, data=None):
        super().tab_event(tab_id, event, data)
        if event == "thought":
            print(f"  [{data.get('kind')}] {data.get('text')}")
