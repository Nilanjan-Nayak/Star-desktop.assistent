"""TabManager: the single source of truth for which tabs exist and which is active."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from .models import TabSpec


class TabManager(QObject):
    opened = Signal(object)          # TabSpec
    closed = Signal(str)
    activated = Signal(str)          # "" when no tab is left
    retitled = Signal(str, str)
    busy_changed = Signal(str, bool)
    user_action = Signal(str, str, object)  # tab_id, action, data  (UI -> core)
    event = Signal(str, str, object)        # tab_id, event, data   (core -> UI)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._specs: dict[str, TabSpec] = {}
        self._active = ""
        self._busy: set[str] = set()

    # queries
    @property
    def specs(self) -> list[TabSpec]:
        return list(self._specs.values())

    @property
    def active_id(self) -> str:
        return self._active

    def count(self) -> int:
        return len(self._specs)

    def is_busy(self, tab_id: str) -> bool:
        return tab_id in self._busy

    # commands
    def open_tab(self, spec: TabSpec) -> None:
        if spec.id in self._specs:
            self.activate(spec.id)
            return
        self._specs[spec.id] = spec
        self.opened.emit(spec)
        self.activate(spec.id)

    def close_tab(self, tab_id: str) -> None:
        if tab_id not in self._specs:
            return
        ids = list(self._specs)
        idx = ids.index(tab_id)
        del self._specs[tab_id]
        self._busy.discard(tab_id)
        self.closed.emit(tab_id)
        if tab_id == self._active:
            self._active = ""
            if self._specs:
                self.activate(list(self._specs)[min(idx, len(self._specs) - 1)])
            else:
                self.activated.emit("")

    def activate(self, tab_id: str) -> None:
        if tab_id in self._specs and tab_id != self._active:
            self._active = tab_id
            self.activated.emit(tab_id)

    def cycle(self, step: int = 1) -> None:
        ids = list(self._specs)
        if len(ids) > 1 and self._active in ids:
            self.activate(ids[(ids.index(self._active) + step) % len(ids)])

    def retitle(self, tab_id: str, title: str) -> None:
        if tab_id in self._specs and self._specs[tab_id].title != title:
            self._specs[tab_id].title = title
            self.retitled.emit(tab_id, title)

    def set_busy(self, tab_id: str, busy: bool) -> None:
        if (tab_id in self._busy) != busy:
            (self._busy.add if busy else self._busy.discard)(tab_id)
            self.busy_changed.emit(tab_id, busy)

    def dispatch(self, tab_id: str, event: str, data) -> None:
        if tab_id in self._specs:
            self.event.emit(tab_id, event, data)
