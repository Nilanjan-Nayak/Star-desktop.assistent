"""Agent workspace: thought-process timeline, live code, output console, run controls."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QSplitter, QVBoxLayout, QWidget

from ..fx import stagger
from ..states import StateModel
from ..theme import THEME
from ..widgets import GhostButton, IconButton, StatusChip
from .base import BaseTab
from .code_view import CodeView, ConsoleView
from .models import TabSpec
from .thought_stream import ThoughtStream

NARROW_BELOW = 600  # px: show one pane at a time with a switcher


def _section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{THEME.dim}; font:600 9pt '{THEME.font}'; background:transparent; padding:2px 2px 4px 2px;")
    return lbl


def _column(*widgets: QWidget) -> QWidget:
    box = QWidget()
    box.setStyleSheet("background:transparent;")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    for w in widgets:
        lay.addWidget(w, 1 if not isinstance(w, QLabel) else 0)
    return box


class AgentTab(BaseTab):
    def __init__(self, model: StateModel, spec: TabSpec, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self._paused = False
        self._seconds = 0

        task = self._task = QLabel(spec.payload.get("task", spec.title))
        task.setStyleSheet(f"color:{THEME.text}; font:600 12pt '{THEME.font}'; background:transparent;")
        task.setMinimumWidth(40)
        self.chip = StatusChip(model)
        self.chip.set_status("running", "Starting")
        self.elapsed = QLabel("00:00")
        self.elapsed.setStyleSheet(f"color:{THEME.dim}; font:10pt '{THEME.mono}'; background:transparent;")
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(task, 1)
        head.addWidget(self.chip)
        head.addWidget(self.elapsed)

        self.thoughts = ThoughtStream(model)
        self.code = CodeView()
        self.console = ConsoleView()

        right = QSplitter(Qt.Vertical)
        right.setHandleWidth(10)
        right.addWidget(_column(_section("Workspace"), self.code))
        right.addWidget(_column(_section("Output"), self.console))
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        right.setStyleSheet("QSplitter::handle{background:transparent;}")

        self.split = QSplitter(Qt.Horizontal)
        self.split.setHandleWidth(12)
        self.split.setStyleSheet("QSplitter::handle{background:transparent;}")
        self.left_pane = _column(_section("Thought process"), self.thoughts)
        self.right_pane = right
        self.split.addWidget(self.left_pane)
        self.split.addWidget(self.right_pane)
        self.split.setStretchFactor(0, 2)
        self.split.setStretchFactor(1, 3)
        self.split.setChildrenCollapsible(False)

        self.btn_pause = GhostButton(model, "Pause", "pause")
        self.btn_stop = GhostButton(model, "Stop", "stop", "danger")
        self.steer = QLineEdit()
        self.steer.setPlaceholderText("Steer the agent, e.g. use a different approach")
        self.steer.setFixedHeight(34)
        self.steer.setStyleSheet(
            f"QLineEdit{{background:rgba(255,255,255,0.06); border:1px solid rgba(155,123,255,0.25);"
            f"border-radius:10px; padding:0 12px; color:{THEME.text}; font:10pt '{THEME.font}';}}"
            f"QLineEdit:focus{{border-color:rgba(155,123,255,0.8);}}")
        self.btn_send = IconButton(model, "send", "Send", 34)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.btn_pause)
        controls.addWidget(self.btn_stop)
        controls.addSpacing(6)
        controls.addWidget(self.steer, 1)
        controls.addWidget(self.btn_send)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 2)
        lay.setSpacing(10)
        self._narrow = False
        self._view = "thoughts"
        self.btn_view_thoughts = GhostButton(model, "Thought process", "", "primary")
        self.btn_view_work = GhostButton(model, "Workspace", "", "ghost")
        self.switcher = QWidget()
        sw = QHBoxLayout(self.switcher)
        sw.setContentsMargins(0, 0, 0, 0)
        sw.setSpacing(8)
        sw.addWidget(self.btn_view_thoughts)
        sw.addWidget(self.btn_view_work)
        sw.addStretch(1)
        self.switcher.hide()
        self.btn_view_thoughts.clicked.connect(lambda: self._set_view("thoughts"))
        self.btn_view_work.clicked.connect(lambda: self._set_view("workspace"))

        lay.addLayout(head)
        lay.addWidget(self.switcher)
        lay.addWidget(self.split, 1)
        lay.addLayout(controls)

        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_stop.clicked.connect(self._stop)
        self.steer.returnPressed.connect(self._send)
        self.btn_send.clicked.connect(self._send)

        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start()
        self.busy_changed.emit(True)
        stagger([self._task, self.chip, self.elapsed, self.left_pane, self.right_pane,
                 self.btn_pause, self.btn_stop, self.steer, self.btn_send], start=0.05, step=0.06)

    # responsive ---------------------------------------------------------------
    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        narrow = self.width() < NARROW_BELOW
        if narrow != self._narrow:
            self._narrow = narrow
            self._apply_view()
        self.btn_pause.setVisible(self.width() > 460)

    def _set_view(self, view: str) -> None:
        self._view = view
        self._apply_view()

    def _apply_view(self) -> None:
        self.switcher.setVisible(self._narrow)
        self.left_pane.setVisible(not self._narrow or self._view == "thoughts")
        self.right_pane.setVisible(not self._narrow or self._view == "workspace")
        self.btn_view_thoughts.set_variant("primary" if self._view == "thoughts" else "ghost")
        self.btn_view_work.set_variant("primary" if self._view == "workspace" else "ghost")

    # controls -------------------------------------------------------------------
    def _tick_clock(self) -> None:
        if not self._paused:
            self._seconds += 1
            self.elapsed.setText(f"{self._seconds // 60:02d}:{self._seconds % 60:02d}")

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.btn_pause.setText("Resume" if self._paused else "Pause")
        self.btn_pause.set_icon("play" if self._paused else "pause")
        self.chip.set_status("paused" if self._paused else "running", "Paused" if self._paused else "Working")
        self.busy_changed.emit(not self._paused)
        self.user_action.emit("pause" if self._paused else "resume", None)

    def _stop(self) -> None:
        self._finish("warning", "Stopped")
        self.user_action.emit("stop", None)

    def _send(self) -> None:
        text = self.steer.text().strip()
        if text:
            self.thoughts.add("observe", f"You: {text}")
            self.user_action.emit("message", text)
            self.steer.clear()

    def _finish(self, kind: str, text: str) -> None:
        self._clock.stop()
        self.chip.set_status(kind, text)
        self.thoughts.settle()
        self.busy_changed.emit(False)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)

    # core -> UI -----------------------------------------------------------------
    def handle_event(self, event: str, data) -> None:
        d = data or {}
        if event == "thought":
            self.thoughts.add(d.get("kind", "think"), d.get("text", ""))
        elif event == "code":
            (self.code.append_code if d.get("append") else self.code.set_code)(d.get("text", ""))
        elif event == "output":
            self.console.append_output(d.get("text", ""))
        elif event == "status":
            kind, text = d.get("kind", "running"), d.get("text", "")
            if kind in ("success", "error", "warning"):
                self._finish(kind, text)
            else:
                self.chip.set_status(kind, text)
        elif event == "title":
            self.title_changed.emit(d.get("text", ""))
