"""GhostTerminal: the glass window that hosts all tabs. Stage animates its size and position."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..states import StateModel
from ..theme import rgba
from ..widgets import GlassFrame, IconButton
from .agent_tab import AgentTab
from .base import BaseTab
from .fade_stack import FadeStack
from .manager import TabManager
from .models import TabKind, TabSpec
from .system_tab import SystemTab
from .tab_bar import GhostTabBar
from .web_tab import WebTab

_FACTORY = {TabKind.WEB: WebTab, TabKind.AGENT: AgentTab, TabKind.SYSTEM: SystemTab}


class GhostTerminal(GlassFrame):
    open_changed = Signal(bool)

    def __init__(self, model: StateModel, manager: TabManager, parent: QWidget | None = None):
        super().__init__(model, radius=18, body_alpha=165, parent=parent)
        self.manager = manager
        self._tabs: dict[str, BaseTab] = {}
        self._open = False
        self._final_w = 640

        # The content is laid out at its final width and merely clipped while Stage grows
        # the window, so opening never makes the tabs (or a web view) re-layout every frame.
        self.content = QWidget(self)
        self.bar = GhostTabBar(model, manager)
        self.stack = FadeStack()
        self.btn_hide = IconButton(model, "minimize", "Hide terminal (Ctrl+`)")
        self.btn_close = IconButton(model, "close", "Close tab (Ctrl+W)")
        top = QHBoxLayout()
        top.setSpacing(2)
        top.addWidget(self.bar, 1)
        top.addWidget(self.btn_hide)
        top.addWidget(self.btn_close)
        lay = QVBoxLayout(self.content)
        lay.setContentsMargins(12, 8, 12, 12)
        lay.setSpacing(8)
        lay.addLayout(top)
        lay.addWidget(self.stack, 1)

        self.btn_hide.clicked.connect(self.hide_terminal)
        self.btn_close.clicked.connect(lambda: manager.close_tab(manager.active_id))
        manager.opened.connect(self._on_opened)
        manager.closed.connect(self._on_closed)
        manager.activated.connect(self._on_activated)
        manager.event.connect(self._on_event)

    # state ----------------------------------------------------------------------------
    @property
    def is_open(self) -> bool:
        return self._open

    def set_final_width(self, w: int) -> None:
        self._final_w = max(320, w)
        self._fit()

    def _fit(self) -> None:
        self.content.setGeometry(0, 0, max(self.width(), self._final_w), self.height())

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._fit()

    def show_terminal(self) -> None:
        if not self._open:
            self._open = True
            self.open_changed.emit(True)

    def hide_terminal(self) -> None:
        if self._open:
            self._open = False
            self.open_changed.emit(False)

    def toggle(self) -> None:
        if self._open:
            self.hide_terminal()
        elif self.manager.count():
            self.show_terminal()

    # manager slots --------------------------------------------------------------------
    def _on_opened(self, spec: TabSpec) -> None:
        tab = _FACTORY[spec.kind](self.model, spec)
        tid = spec.id
        tab.busy_changed.connect(lambda b, i=tid: self.manager.set_busy(i, b))
        tab.title_changed.connect(lambda t, i=tid: self.manager.retitle(i, t))
        tab.user_action.connect(lambda a, d, i=tid: self.manager.user_action.emit(i, a, d))
        tab.request_close.connect(lambda i=tid: self.manager.close_tab(i))
        self._tabs[tid] = tab
        self.stack.addWidget(tab)
        self.show_terminal()

    def _on_closed(self, tab_id: str) -> None:
        tab = self._tabs.pop(tab_id, None)
        if tab is not None:
            self.stack.removeWidget(tab)
            tab.deleteLater()
        if not self._tabs:
            self.hide_terminal()

    def _on_activated(self, tab_id: str) -> None:
        if tab_id in self._tabs:
            self.stack.fade_to(self._tabs[tab_id])

    def _on_event(self, tab_id: str, event: str, data) -> None:
        if tab_id in self._tabs:
            self._tabs[tab_id].handle_event(event, data)

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        p = QPainter(self)
        y = self.bar.geometry().bottom() + 4
        g = QLinearGradient(12, 0, self.width() - 12, 0)
        col = self.model.style.color
        g.setColorAt(0.0, rgba(col, 0))
        g.setColorAt(0.2, rgba(col, 70))
        g.setColorAt(0.8, rgba(col, 70))
        g.setColorAt(1.0, rgba(col, 0))
        p.setPen(QPen(g, 1))
        p.drawLine(12, y, self.width() - 12, y)
