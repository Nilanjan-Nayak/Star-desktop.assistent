"""Full-window backdrop: depth glow, perspective floor, drifting dust, scan sweep, vignette."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from .states import StateModel
from .theme import THEME, rgba


class BackgroundField(QWidget):
    """Container widget: put the rest of the UI inside it."""

    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        rnd = random.Random(3)
        self._dust = [[rnd.random(), rnd.random(), rnd.random()] for _ in range(80)]
        model.ticked.connect(self._on_tick)

    def _on_tick(self, dt: float) -> None:
        for d in self._dust:
            d[1] -= dt * 0.012 * (0.3 + d[2])
            d[0] += dt * 0.004 * (d[2] - 0.5)
            d[1] %= 1.0
            d[0] %= 1.0
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = self.model.time
        col = self.model.style.color
        centre = QPointF(w / 2, h * 0.46)

        base = QRadialGradient(centre, max(w, h) * 0.75)
        base.setColorAt(0.0, QColor(THEME.deep))
        base.setColorAt(1.0, QColor(THEME.void))
        p.fillRect(self.rect(), base)

        glow = QRadialGradient(centre, min(w, h) * 0.7)
        glow.setColorAt(0.0, rgba(col, 28))
        glow.setColorAt(1.0, rgba(col, 0))
        p.fillRect(self.rect(), glow)

        p.setOpacity(self.model.intro.p(0.0, 1.4))
        self._floor(p, w, h, t, col)
        p.setOpacity(1.0)
        self._dust_layer(p, w, h, t, col)
        self._sweep(p, w, h, t, col)

        vig = QRadialGradient(centre, max(w, h) * 0.72)
        vig.setColorAt(0.55, rgba(THEME.void, 0))
        vig.setColorAt(1.0, rgba(THEME.void, 200))
        p.fillRect(self.rect(), vig)

    def _floor(self, p: QPainter, w: int, h: int, t: float, col: QColor) -> None:
        horizon, cx = h * 0.68, w / 2
        fade = QLinearGradient(0, horizon, 0, h)
        fade.setColorAt(0.0, rgba(col, 0))
        fade.setColorAt(1.0, rgba(col, 50))
        p.setPen(QPen(QBrush(fade), 1))
        for i in range(-16, 17):
            p.drawLine(QPointF(cx + i * w * 0.012, horizon), QPointF(cx + i * w * 0.11, h))
        n = 10
        for k in range(n):
            z = ((k + t * 0.35) % n) / n
            y = horizon + (h - horizon) * z ** 2.0
            p.setPen(QPen(rgba(col, 70 * z), 1))
            p.drawLine(QPointF(0, y), QPointF(w, y))
        line = QLinearGradient(0, 0, w, 0)
        line.setColorAt(0.0, rgba(col, 0))
        line.setColorAt(0.5, rgba(col, 90))
        line.setColorAt(1.0, rgba(col, 0))
        p.setPen(QPen(QBrush(line), 1))
        p.drawLine(QPointF(0, horizon), QPointF(w, horizon))

    def _dust_layer(self, p: QPainter, w: int, h: int, t: float, col: QColor) -> None:
        p.setPen(Qt.NoPen)
        for i, (x, y, z) in enumerate(self._dust):
            tw = 0.5 + 0.5 * math.sin(t * 1.3 + i)
            p.setBrush(rgba(col, 25 + 70 * z * tw))
            r = 0.6 + 1.4 * z
            p.drawEllipse(QPointF(x * w, y * h), r, r)

    def _sweep(self, p: QPainter, w: int, h: int, t: float, col: QColor) -> None:
        y = ((t * 0.09) % 1.3 - 0.15) * h
        band = QLinearGradient(0, y - 45, 0, y + 45)
        band.setColorAt(0.0, rgba(col, 0))
        band.setColorAt(0.5, rgba(col, 16))
        band.setColorAt(1.0, rgba(col, 0))
        p.fillRect(0, int(y - 45), w, 90, band)
