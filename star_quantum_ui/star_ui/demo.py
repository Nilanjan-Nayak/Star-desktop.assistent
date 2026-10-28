"""Fake assistant so the UI can be explored without STAR's core. Not needed in production.

Try typing:  "open youtube"  |  "install ripgrep"  |  "write a slugify function"  |  anything else
"""
from __future__ import annotations

import random

from PySide6.QtCore import QObject, QTimer

from .bridge import UIBridge

CODE = '''import re


def slugify(title: str) -> str:
    """Turn a title into a URL-safe slug."""
    text = title.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


assert slugify("Hello, World!") == "hello-world"
assert slugify("  Ghost   Terminal ") == "ghost-terminal"
assert slugify("") == ""
print("3 passed")
'''


class DemoDriver(QObject):
    def __init__(self, bridge: UIBridge, parent: QObject | None = None):
        super().__init__(parent)
        self.bridge = bridge
        self._rng = random.Random(11)
        self._n = 0
        self._stopped: set[str] = set()
        self._vals = {"Latency": 140.0, "Throughput": 38.0, "Memory nodes": 1280.0, "Skills": 24.0}
        bridge.user_text.connect(self.on_user_text)
        bridge.tab_action.connect(self._on_tab_action)

        self._metrics = QTimer(self)
        self._metrics.setInterval(700)
        self._metrics.timeout.connect(self._feed_metrics)
        self._metrics.start()

        self._level = QTimer(self)
        self._level.setInterval(60)
        self._level.timeout.connect(lambda: bridge.level.emit(0.25 + 0.75 * self._rng.random()))

    # helpers -----------------------------------------------------------------
    def _feed_metrics(self) -> None:
        v = self._vals
        v["Latency"] = max(40.0, v["Latency"] + self._rng.uniform(-18, 18))
        v["Throughput"] = max(5.0, v["Throughput"] + self._rng.uniform(-4, 4))
        if self._rng.random() < 0.4:
            v["Memory nodes"] += self._rng.randint(1, 4)
        if self._rng.random() < 0.05:
            v["Skills"] += 1
        for k, val in v.items():
            self.bridge.metric.emit(k, val)

    def _new_id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}-{self._n}"

    def _play(self, tab_id: str, script, start: int = 0) -> int:
        """script: [(delay_ms, event, data)] relative to the previous item. Returns end time."""
        t = start
        for delay, event, data in script:
            t += delay
            QTimer.singleShot(t, lambda e=event, d=data: None if tab_id in self._stopped
                              else self.bridge.tab_event.emit(tab_id, e, d))
        return t

    def _say(self, text: str, hold: int = 2000) -> None:
        b = self.bridge
        b.state.emit("speaking")
        b.message.emit(text)
        self._level.start()
        QTimer.singleShot(hold, self._finish)

    def _finish(self) -> None:
        self._level.stop()
        self.bridge.level.emit(-1.0)
        self.bridge.state.emit("idle")
        self.bridge.message.emit("Standing by. Type a command below.")

    # routing -----------------------------------------------------------------
    def on_user_text(self, text: str) -> None:
        low = text.lower()
        if "youtube" in low or low.startswith("open "):
            self._demo_web(text, low)
        elif "install" in low:
            self._demo_install(text)
        elif any(k in low for k in ("code", "write", "script", "function", "build", "fix", "debug")):
            self._demo_agent(text)
        else:
            self._demo_chat(text)

    def _on_tab_action(self, tab_id: str, action: str, data) -> None:
        b = self.bridge
        if action == "cancel":
            b.tab_close.emit(tab_id)
        elif action == "stop":
            self._stopped.add(tab_id)
        elif action == "message":
            b.tab_event.emit(tab_id, "thought", {"kind": "observe", "text": f"Noted your steer: \"{data}\". Adjusting the plan."})
        elif action == "approve" and tab_id.startswith("sys"):
            self._run_install(tab_id)

    # flows -------------------------------------------------------------------
    def _demo_chat(self, text: str) -> None:
        b = self.bridge
        b.state.emit("listening")
        b.message.emit("Got it.")
        QTimer.singleShot(900, lambda: (b.state.emit("thinking"),
                                        b.message.emit(f"Routing \"{text}\" to the planner agent.")))
        QTimer.singleShot(3000, lambda: self._say(f"Done. I handled \"{text}\" and logged it to memory.", 2600))

    def _demo_web(self, text: str, low: str) -> None:
        b = self.bridge
        if "youtube" in low:
            title, url = "YouTube", "https://www.youtube.com"
        else:
            target = text.split(None, 1)[1].strip()
            title, url = target, target if "." in target else f"{target}.com"
        b.state.emit("thinking")
        b.message.emit(f"Opening {title}...")
        QTimer.singleShot(800, lambda: (b.tab_open.emit(self._new_id("web"), "web", title, {"url": url}),
                                        self._say(f"Opened {title} in a new tab.", 1800)))

    def _demo_agent(self, text: str) -> None:
        b = self.bridge
        tid = self._new_id("agent")
        b.state.emit("thinking")
        b.message.emit("Spinning up an agent workspace...")

        def start():
            b.tab_open.emit(tid, "agent", text[:40], {"task": text})
            script = [
                (500, "status", {"kind": "running", "text": "Working"}),
                (600, "thought", {"kind": "think", "text": "Break the request into steps: define the behaviour, write the function, check edge cases."}),
                (1500, "thought", {"kind": "tool", "text": 'workspace.write("slugify.py")'}),
            ]
            end = self._play(tid, script)
            lines = CODE.splitlines(keepends=True)
            for i in range(0, len(lines), 3):
                end += 420
                chunk = "".join(lines[i:i + 3])
                QTimer.singleShot(end, lambda c=chunk: None if tid in self._stopped
                                  else b.tab_event.emit(tid, "code", {"text": c, "append": True}))
            tail = [
                (700, "thought", {"kind": "tool", "text": 'shell.run("python slugify.py")'}),
                (900, "output", {"text": "$ python slugify.py\n3 passed"}),
                (600, "thought", {"kind": "observe", "text": "All three checks pass, including the empty string."}),
                (800, "thought", {"kind": "result", "text": "Wrote slugify.py and verified it. Ready for your review."}),
                (300, "status", {"kind": "success", "text": "Done"}),
            ]
            self._play(tid, tail, end)
            QTimer.singleShot(1200, lambda: self._say("I opened an agent workspace. You can follow my reasoning there.", 2200))

        QTimer.singleShot(800, start)

    def _demo_install(self, text: str) -> None:
        b = self.bridge
        words = [w.strip(".,!?\"'") for w in text.split()]
        pkg = words[-1] if words and words[-1].lower() != "install" else "ripgrep"
        tid = self._new_id("sys")
        b.state.emit("thinking")
        b.message.emit(f"Looking up {pkg}...")

        def start():
            b.tab_open.emit(tid, "system", f"Install {pkg}", {
                "package": pkg,
                "description": f"{pkg} is not on this machine yet. STAR knows how to install it; review before it runs.",
                "info": {"Package": pkg, "Version": "14.1.0", "Source": "apt, ubuntu/main", "Size": "6.2 MB",
                         "Needs": "sudo", "Checksum": "verified"},
                "steps": ["Resolve dependencies", "Download", "Install", "Verify"],
            })
            b.tab_event.emit(tid, "log", f"$ apt-cache policy {pkg}")
            b.tab_event.emit(tid, "log", f"{pkg}: candidate 14.1.0, 6.2 MB")
            b.tab_event.emit(tid, "awaiting_approval", None)
            self._say(f"I found {pkg}. Approve the install in the new tab when you are ready.", 2200)

        QTimer.singleShot(900, start)

    def _run_install(self, tid: str) -> None:
        S = lambda i, st, d="": (0, "step", {"index": i, "state": st, "detail": d})
        script = [
            (200, "status", {"kind": "running", "text": "Installing"}),
            S(0, "active"), (500, "log", "Reading package lists... done"), (400, "progress", 0.12),
            S(0, "done", "0.9s"), S(1, "active"),
            (500, "log", "Get:1 http://archive.ubuntu.com 6.2 MB"), (500, "progress", 0.35),
            (600, "progress", 0.6), S(1, "done", "1.4s"), S(2, "active"),
            (500, "log", "Unpacking..."), (500, "progress", 0.8), (500, "log", "Setting up..."),
            S(2, "done", "1.1s"), S(3, "active"), (600, "log", "$ --version -> OK"), (400, "progress", 1.0),
            S(3, "done", "0.3s"), (300, "finished", {"ok": True, "text": "Installed"}),
        ]
        self._play(tid, script)
