"""GlassFrame: translucent frosted-style surface tinted by the current assistant state.

Qt widgets can't blur what is behind them, so the frosted look is simulated with layered
gradients: dark body, state-colour tint, a slow moving sheen, a top highlight and a hairline edge.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..states import StateModel
from ..theme import THEME, rgba


class GlassFrame(QWidget):
    def __init__(self, model: StateModel, radius: float = 16, body_alpha: int = 150,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.radius = radius
        self.body_alpha = body_alpha
        model.ticked.connect(self._tick)

    def _tick(self, _dt: float) -> None:
        if self.isVisible():
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, r = self.width(), self.height(), self.radius
        col, t = self.model.style.color, self.model.time

        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)

        body = QLinearGradient(0, 0, w * 0.6, h)
        body.setColorAt(0.0, rgba("#10232e", self.body_alpha))
        body.setColorAt(1.0, rgba(THEME.void, min(255, self.body_alpha + 30)))
        p.fillPath(path, body)

        tint = QLinearGradient(0, 0, 0, h)
        tint.setColorAt(0.0, rgba(col, 30))
        tint.setColorAt(0.5, rgba(col, 6))
        tint.setColorAt(1.0, rgba(col, 0))
        p.fillPath(path, tint)

        p.save()
        p.setClipPath(path)
        x = ((t * 0.05) % 1.6 - 0.3) * w
        sheen = QLinearGradient(x - 110, 0, x + 110, 0)
        sheen.setColorAt(0.0, rgba("#ffffff", 0))
        sheen.setColorAt(0.5, rgba("#ffffff", 13))
        sheen.setColorAt(1.0, rgba("#ffffff", 0))
        p.fillRect(self.rect(), sheen)
        p.restore()

        hl = QLinearGradient(0, 0, w, 0)
        hl.setColorAt(0.0, rgba("#ffffff", 0))
        hl.setColorAt(0.3, rgba("#ffffff", 110))
        hl.setColorAt(1.0, rgba("#ffffff", 0))
        p.setPen(QPen(hl, 1))
        p.drawLine(int(r), 1, int(w - r), 1)

        p.setPen(QPen(rgba(col, 70), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

