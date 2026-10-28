"""Row of state buttons for manual testing and quick overrides."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from .states import STATES, StateModel
from .theme import THEME


class StateChips(QWidget):
    selected = Signal(str)

    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        style = (
            f"QPushButton{{color:{THEME.dim}; background:transparent;"
            f"border:1px solid {THEME.grid}; padding:8px 16px; font:10pt '{THEME.font}';}}"
            f"QPushButton:hover{{color:{THEME.text}; border-color:{THEME.dim};}}"
            f"QPushButton:checked{{color:{THEME.cyan}; border-color:{THEME.cyan};"
            f"background:rgba(79,240,255,0.08);}}")
        for name in STATES:
            b = QPushButton(name.capitalize())
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet(style)
            self._group.addButton(b)
            self._buttons[name] = b
            b.clicked.connect(lambda _=False, n=name: self.selected.emit(n))
            lay.addWidget(b)
        self.sync(model.name)
        model.changed.connect(self.sync)

    def sync(self, name: str) -> None:
        if name in self._buttons:
            self._buttons[name].setChecked(True)
