"""Slim progress bar with glow, moving highlight and an indeterminate mode."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from ..states import StateModel
from ..theme import rgba


class GlowProgress(QWidget):
    def __init__(self, model: StateModel, height: int = 8, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.setFixedHeight(height + 8)
        self._bar_h = height
        self._v = 0.0
        self._target = 0.0
        self._indet = False
        model.ticked.connect(self._tick)

    def set_value(self, v: float) -> None:
        self._indet = False
        self._target = max(0.0, min(1.0, v))

    def set_indeterminate(self, on: bool) -> None:
        self._indet = on

    def value(self) -> float:
        return self._target

    def _tick(self, dt: float) -> None:
        self._v += (self._target - self._v) * min(1.0, dt * 6)
        if self.isVisible():
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        col, t = self.model.style.color, self.model.time
        bh = self._bar_h
        y = (self.height() - bh) / 2
        track = QPainterPath()
        track.addRoundedRect(QRectF(0, y, w, bh), bh / 2, bh / 2)
        p.fillPath(track, rgba("#ffffff", 16))

        if self._indet:
            seg = w * 0.28
            x0 = ((t * 0.9) % 1.5 - 0.25) * w
            x1 = x0 + seg
        else:
            x0, x1 = 0.0, w * self._v
        if x1 - x0 < 1:
            return
        p.save()
        p.setClipPath(track)
        fill = QLinearGradient(x0, 0, x1, 0)
        fill.setColorAt(0.0, rgba(col, 90))
        fill.setColorAt(1.0, rgba(col, 255))
        glow = QLinearGradient(x0, 0, x1, 0)
        glow.setColorAt(0.0, rgba(col, 0))
        glow.setColorAt(1.0, rgba(col, 70))
        p.fillRect(QRectF(x0, y - 4, x1 - x0, bh + 8), glow)
        p.fillRect(QRectF(x0, y, x1 - x0, bh), fill)
        hx = x0 + ((t * 1.3) % 1.0) * (x1 - x0)
        shine = QLinearGradient(hx - 24, 0, hx + 24, 0)
        shine.setColorAt(0.0, rgba("#ffffff", 0))
        shine.setColorAt(0.5, rgba("#ffffff", 120))
        shine.setColorAt(1.0, rgba("#ffffff", 0))
        p.fillRect(QRectF(x0, y, x1 - x0, bh), shine)
        p.restore()
        p.setPen(Qt.NoPen)
        p.setBrush(rgba("#ffffff", 230))
        p.drawEllipse(QRectF(x1 - bh / 2, y, bh, bh))
