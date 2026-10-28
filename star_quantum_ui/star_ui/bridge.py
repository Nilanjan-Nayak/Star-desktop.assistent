"""Thread-safe seam between STAR's core (event bus, LLM router) and the UI.

Emit these signals from ANY thread; Qt queues them onto the GUI thread.

    bridge.state.emit("thinking")           # idle | listening | thinking | speaking
    bridge.message.emit("Opening the repo")  # text for the ghost panel
    bridge.level.emit(0.7)                   # live audio level 0..1, or -1 for procedural
    bridge.metric.emit("Latency", 132.0)     # see telemetry.METRICS

Ghost terminal tabs:

    bridge.tab_open.emit("t1", "web", "YouTube", {"url": "https://www.youtube.com"})
    bridge.tab_open.emit("t2", "agent", "Fix parser", {"task": "Fix the CSV parser"})
    bridge.tab_event.emit("t2", "thought", {"kind": "think", "text": "Read the failing test first"})
    bridge.tab_event.emit("t2", "code", {"text": "def parse(): ...", "append": False})
    bridge.tab_event.emit("t2", "output", {"text": "3 passed"})
    bridge.tab_event.emit("t2", "status", {"kind": "success", "text": "Done"})
    bridge.tab_open.emit("t3", "system", "Install ripgrep",
                         {"package": "ripgrep", "info": {"Version": "14.1"}, "steps": ["Download", "Install"]})
    bridge.tab_event.emit("t3", "awaiting_approval", None)   # shows Approve / Cancel
    bridge.tab_action.connect(...)                           # receives "approve", "cancel", "stop", ...

The UI emits `user_text` when the person submits a command; subscribe to it from the core.

Example event-bus glue (adapt names to your bus):

    bus.subscribe("assistant.state",   lambda s: bridge.state.emit(s))
    bus.subscribe("assistant.reply",   lambda t: bridge.message.emit(t))
    bridge.user_text.connect(lambda t: bus.publish("user.command", t))
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class UIBridge(QObject):
    # core -> UI
    state = Signal(str)
    message = Signal(str)
    level = Signal(float)
    metric = Signal(str, float)
    tab_open = Signal(str, str, str, object)   # tab_id, kind ("web"|"agent"|"system"), title, payload dict
    tab_close = Signal(str)                    # tab_id
    tab_event = Signal(str, str, object)       # tab_id, event, data  (see tabs/*_tab.py handle_event)
    # UI -> core
    user_text = Signal(str)
    tab_action = Signal(str, str, object)      # tab_id, action ("approve", "cancel", "pause", "stop", "message"...), data
