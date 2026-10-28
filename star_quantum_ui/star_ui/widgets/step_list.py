"""Vertical checklist with a connector rail: pending, active (pulsing), done, failed."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..motion import ease_out_cubic
from ..states import StateModel
from ..theme import THEME, rgba
from .icons import draw_icon


class StepList(QWidget):
    ROW = 34

    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self._steps: list[list] = []  # [label, state, detail]
        self._born = 0.0
        self._flash: dict[int, float] = {}
        model.ticked.connect(self._on_tick)

    def _on_tick(self, _dt: float) -> None:
        if self.isVisible():
            self.update()

    def set_steps(self, labels: list[str]) -> None:
        self._steps = [[l, "pending", ""] for l in labels]
        self._born = self.model.time
        self._flash = {}
        self.setFixedHeight(self.ROW * len(labels))
        self.update()

    def set_state(self, index: int, state: str, detail: str = "") -> None:
        if 0 <= index < len(self._steps):
            if self._steps[index][1] != state:
                self._flash[index] = self.model.time
            self._steps[index][1] = state
            if detail:
                self._steps[index][2] = detail
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col, t = self.model.style.color, self.model.time
        n = len(self._steps)
        for i, (label, state, detail) in enumerate(self._steps):
            rp = ease_out_cubic((t - self._born - 0.09 * i - 0.1) / 0.45)
            if rp <= 0:
                continue
            p.save()
            p.setOpacity(rp)
            p.translate(-(1 - rp) * 18, 0)
            cy = i * self.ROW + self.ROW / 2
            cx = 12
            if i < n - 1:
                done = state == "done"
                p.setPen(QPen(rgba(THEME.mint if done else THEME.dim, 150 if done else 55), 1.2))
                p.drawLine(QPointF(cx, cy + 10), QPointF(cx, cy + self.ROW - 10))
            ring = QRectF(cx - 8, cy - 8, 16, 16)
            if state == "done":
                p.setBrush(rgba(THEME.mint, 40))
                p.setPen(QPen(rgba(THEME.mint, 220), 1.4))
                p.drawEllipse(ring)
                draw_icon(p, "check", ring.adjusted(3.5, 3.5, -3.5, -3.5), rgba(THEME.mint, 255), 1.5)
                fg = THEME.text
            elif state == "failed":
                p.setBrush(rgba(THEME.red, 40))
                p.setPen(QPen(rgba(THEME.red, 220), 1.4))
                p.drawEllipse(ring)
                draw_icon(p, "close", ring.adjusted(4, 4, -4, -4), rgba(THEME.red, 255), 1.5)
                fg = THEME.red
            elif state == "active":
                pulse = 0.5 + 0.5 * math.sin(t * 5)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(rgba(col, 90 + 150 * pulse), 1.6))
                p.drawEllipse(ring.adjusted(-pulse * 2, -pulse * 2, pulse * 2, pulse * 2))
                p.setPen(Qt.NoPen)
                p.setBrush(rgba(col, 255))
                p.drawEllipse(QPointF(cx, cy), 3.2, 3.2)
                fg = THEME.text
            else:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(rgba(THEME.dim, 120), 1.2))
                p.drawEllipse(ring)
                fg = THEME.dim
            p.setFont(QFont(THEME.font, 10))
            p.setPen(rgba(fg, 255))
            p.drawText(QPointF(36, cy + 4), label)
            if detail:
                p.setFont(QFont(THEME.mono, 9))
                p.setPen(rgba(THEME.dim, 255))
                adv = p.fontMetrics().horizontalAdvance(detail)
                p.drawText(QPointF(self.width() - adv - 4, cy + 4), detail)
            fl = (t - self._flash.get(i, -9.0)) / 0.55
            if 0 <= fl < 1:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(rgba(col if state == "active" else THEME.mint, 170 * (1 - fl)), 1.4))
                p.drawEllipse(QPointF(cx, cy), 8 + 12 * fl, 8 + 12 * fl)
            p.restore()
