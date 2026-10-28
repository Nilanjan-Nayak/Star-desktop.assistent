"""Assembles every element into the STAR window; Stage animates the arrangement."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from . import fx
from .background import BackgroundField
from .bridge import UIBridge
from .command_bar import CommandBar
from .ghost_panel import GhostPanel
from .header import HeaderBar
from .layout_rules import arrange, plan_for
from .reactor import QuantumReactor
from .stage import Stage
from .state_chips import StateChips
from .states import StateModel
from .tabs import GhostTerminal, TabKind, TabManager, TabSpec
from .telemetry import TelemetryPanel
from .waveform import WaveformBar
from .widgets import GhostButton


class MainWindow(QWidget):
    def __init__(self, model: StateModel, bridge: UIBridge):
        super().__init__()
        self.model, self.bridge = model, bridge
        self.setWindowTitle("STAR")
        self.resize(1280, 780)
        self.setMinimumSize(720, 560)
        self._booted = False

        self.background = BackgroundField(model, self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.background)

        self.tabs = TabManager(self)
        self.header = HeaderBar(model)
        self.telemetry = TelemetryPanel(model)
        self.reactor = QuantumReactor(model)
        self.ghost = GhostPanel(model)
        self.terminal = GhostTerminal(model, self.tabs)
        self.waveform = WaveformBar(model)
        self.command = CommandBar(model)
        self.btn_terminal = GhostButton(model, "Terminal", "agent", "primary")
        self.btn_terminal.hide()
        self.chips = StateChips(model)
        self.chips.hide()

        # Stage places the four main panels and glides them whenever the arrangement changes.
        self.stage = Stage(model)
        self.stage.setMinimumHeight(200)
        self.stage.add("telemetry", self.telemetry, exit_offset=(-46, 0))
        self.stage.add("reactor", self.reactor, scale_in=0.82)
        self.stage.add("ghost", self.ghost, exit_offset=(46, 0), opacity_cb=self.ghost.set_stage_opacity)
        self.stage.add("terminal", self.terminal, collapse=True)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        bottom.addWidget(self.command, 1)
        bottom.addWidget(self.btn_terminal)

        self._col = QVBoxLayout(self.background)
        self._col.setContentsMargins(40, 20, 40, 24)
        self._col.setSpacing(10)
        self._col.addWidget(self.header)
        self._col.addWidget(self.stage, 1)
        self._col.addWidget(self.waveform)
        self._col.addLayout(bottom)

        # core -> UI
        bridge.state.connect(model.set_state)
        bridge.message.connect(self.ghost.show_text)
        bridge.level.connect(self.waveform.set_level)
        bridge.metric.connect(self.telemetry.push)
        bridge.tab_open.connect(self._open_tab)
        bridge.tab_close.connect(self.tabs.close_tab)
        bridge.tab_event.connect(self.tabs.dispatch)
        # UI -> core
        self.command.submitted.connect(bridge.user_text)
        self.tabs.user_action.connect(bridge.tab_action)
        self.chips.selected.connect(model.set_state)
        # arrangement reacts to these
        self.stage.resized.connect(self._apply_layout)
        self.terminal.open_changed.connect(lambda _o: self._apply_layout())
        self.tabs.opened.connect(lambda _s: self._apply_layout())
        self.tabs.closed.connect(lambda _i: self._apply_layout())
        self.btn_terminal.clicked.connect(self.terminal.toggle)

        self._shortcuts()

    # boot -----------------------------------------------------------------------------
    def showEvent(self, e) -> None:
        super().showEvent(e)
        if not self._booted:
            self._booted = True
            QTimer.singleShot(0, self.replay_intro)

    def replay_intro(self) -> None:
        """Play the whole creation sequence again (Ctrl+R)."""
        self.model.intro.start()
        self.stage.replay()
        self._apply_layout()
        fx.fade_in(self.command, 0.9, 0.7)
        self.ghost.hide_panel()
        QTimer.singleShot(1300, lambda: self.ghost.show_text("Standing by. Type a command below or speak freely."))

    # tabs -----------------------------------------------------------------------------
    def _open_tab(self, tab_id: str, kind: str, title: str, payload) -> None:
        self.tabs.open_tab(TabSpec(tab_id, TabKind(kind), title, dict(payload or {})))

    # responsive arrangement -----------------------------------------------------------
    @staticmethod
    def _toggle(widget: QWidget, on: bool) -> None:
        if on and widget.isHidden():
            widget.show()
            fx.fade_in(widget, 0.0, 0.35)
        elif not on and not widget.isHidden():
            widget.hide()

    def _apply_layout(self) -> None:
        if not self._booted:
            return
        plan = plan_for(self.width(), self.height(), self.terminal.is_open)
        self._col.setContentsMargins(plan.margin, 20, plan.margin, 24)
        self._toggle(self.waveform, plan.waveform)
        self.chips.hide()
        self._toggle(self.btn_terminal, self.tabs.count() > 0 and not self.terminal.is_open)
        self.terminal.set_final_width(plan.terminal_width)
        self.stage.arrange(arrange(plan, self.stage.width(), self.stage.height(), self.terminal.is_open))

    # keys -----------------------------------------------------------------------------
    def _shortcuts(self) -> None:
        for i, name in enumerate(["idle", "listening", "thinking", "speaking"], start=1):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, activated=lambda n=name: self.model.set_state(n))
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self._toggle_ghost)
        QShortcut(QKeySequence("Ctrl+`"), self, activated=self.terminal.toggle)
        QShortcut(QKeySequence("Ctrl+W"), self, activated=lambda: self.tabs.close_tab(self.tabs.active_id))
        QShortcut(QKeySequence("Ctrl+Tab"), self, activated=lambda: self.tabs.cycle(1))
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, activated=lambda: self.tabs.cycle(-1))
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.replay_intro)
        QShortcut(QKeySequence("F11"), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence("Esc"), self, activated=self.close)

    def _toggle_ghost(self) -> None:
        if self.ghost.is_shown():
            self.ghost.hide_panel()
        else:
            self.ghost.show_text("Ghost panel restored.")

    def _toggle_fullscreen(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()
