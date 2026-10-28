"""Top bar: wordmark, live state, clock."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, QTime
from PySide6.QtGui import QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .states import StateModel
from .theme import THEME, rgba


class HeaderBar(QWidget):
    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.setFixedHeight(56)
        model.ticked.connect(self._on_tick)

    def _on_tick(self, _dt: float) -> None:
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        col = self.model.style.color

        word = QFont(THEME.font, 17, QFont.DemiBold)
        ip = self.model.intro.p(0.1, 0.9)
        word.setLetterSpacing(QFont.AbsoluteSpacing, 8 + 34 * (1 - ip))
        p.setOpacity(ip)
        p.setFont(word)
        p.setPen(rgba(THEME.text, 255))
        p.drawText(QPointF(0, 26), "STAR")
        p.setOpacity(self.model.intro.p(0.5, 0.6))

        p.setFont(QFont(THEME.font, 9))
        p.setPen(rgba(col, 255))
        p.drawText(QPointF(2, 46), self.model.style.label)

        p.setFont(QFont(THEME.mono, 12))
        p.setPen(rgba(THEME.dim, 255))
        clock = QTime.currentTime().toString("HH:mm:ss")
        adv = p.fontMetrics().horizontalAdvance(clock)
        p.drawText(QPointF(w - adv, 26), clock)

        line = QLinearGradient(0, 0, w, 0)
        line.setColorAt(0.0, rgba(col, 120))
        line.setColorAt(0.6, rgba(col, 20))
        line.setColorAt(1.0, rgba(col, 0))
        p.setPen(QPen(line, 1))
        p.drawLine(QPointF(0, h - 1), QPointF(w, h - 1))
