"""StatusChip (pill with pulsing dot) and IconBadge (tinted rounded square with an icon)."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QPointF, QRectF, QSize
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..states import StateModel
from ..theme import THEME, rgba
from .icons import draw_icon


class StatusChip(QWidget):
    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self._kind, self._text = "running", ""
        self.setFixedHeight(26)
        model.ticked.connect(self._on_tick)

    def _on_tick(self, _dt: float) -> None:
        if self._kind == "running":
            self.update()

    def set_status(self, kind: str, text: str) -> None:
        self._kind, self._text = kind, text
        self.updateGeometry()
        self.update()

    def _color(self):
        return {"success": THEME.mint, "warning": THEME.amber, "error": THEME.red,
                "paused": THEME.dim}.get(self._kind, self.model.style.color)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(QFont(THEME.font, 9))
        return QSize(fm.horizontalAdvance(self._text) + 38, 26)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = self._color()
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setBrush(rgba(col, 28))
        p.setPen(QPen(rgba(col, 120), 1))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        pulse = 1 + 0.25 * math.sin(self.model.time * 5) if self._kind == "running" else 1
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(col, 255))
        p.drawEllipse(QPointF(14, self.height() / 2), 3.2 * pulse, 3.2 * pulse)
        p.setFont(QFont(THEME.font, 9))
        p.setPen(rgba(col, 255))
        p.drawText(QPointF(26, self.height() / 2 + 4), self._text)


class IconBadge(QWidget):
    def __init__(self, model: StateModel, icon: str, color: str, size: int = 42,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._icon, self._color = icon, color
        self.setFixedSize(size, size)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setBrush(rgba(self._color, 26))
        p.setPen(QPen(rgba(self._color, 110), 1))
        p.drawRoundedRect(r, 12, 12)
        draw_icon(p, self._icon, r.adjusted(11, 11, -11, -11), rgba(self._color, 255), 1.7)
