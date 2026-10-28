"""FlowGrid: items flow into 1 or 2 columns and glide between slots when the width changes."""
from __future__ import annotations

import math

from PySide6.QtWidgets import QWidget

from ..fx import fade_in
from ..motion import Spring
from ..states import StateModel


class FlowGrid(QWidget):
    GAP = 24

    def __init__(self, model: StateModel, row_h: int = 46, min_col_w: int = 230,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.row_h, self.min_col_w = row_h, min_col_w
        self._items: list[list] = []  # [widget, x spring, y spring]
        self._col_w = 100
        self._fresh = True
        model.ticked.connect(self._tick)

    def set_items(self, widgets: list[QWidget]) -> None:
        for it in self._items:
            it[0].deleteLater()
        self._items = []
        for i, w in enumerate(widgets):
            w.setParent(self)
            w.show()
            self._items.append([w, Spring(0, 240), Spring(0, 240)])
            fade_in(w, 0.05 + i * 0.07, 0.4)
        self._fresh = True
        self._retarget()

    def _retarget(self) -> None:
        width = max(1, self.width())
        cols = max(1, min(2, width // self.min_col_w))
        self._col_w = (width - self.GAP * (cols - 1)) / cols
        for i, (_w, sx, sy) in enumerate(self._items):
            sx.target = (i % cols) * (self._col_w + self.GAP)
            sy.target = (i // cols) * self.row_h
            if self._fresh:
                sx.snap()
                sy.snap()
        self._fresh = self.width() <= 1
        rows = math.ceil(len(self._items) / cols) if self._items else 0
        self.setFixedHeight(max(1, rows * self.row_h))

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._retarget()

    def _tick(self, dt: float) -> None:
        if not self.isVisible():
            return
        for w, sx, sy in self._items:
            sx.update(dt)
            sy.update(dt)
            w.setGeometry(round(sx.x), round(sy.x), round(self._col_w), self.row_h)
