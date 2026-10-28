"""Contract every tab content widget follows."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class BaseTab(QWidget):
    busy_changed = Signal(bool)      # shows a pulsing ring on the tab icon
    title_changed = Signal(str)
    user_action = Signal(str, object)  # (action, data) -> forwarded to the core
    request_close = Signal()

    def handle_event(self, event: str, data) -> None:  # pragma: no cover - overridden
        """Receive an event pushed from the core (see bridge.tab_event)."""
