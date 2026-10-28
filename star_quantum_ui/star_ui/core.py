"""The reactor core: halo, unstable shells, counter-rotating lattice, hot centre."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QPolygonF, QRadialGradient

from .theme import rgba


def _hexagon(r: float) -> QPolygonF:
    return QPolygonF([QPointF(r * math.cos(math.radians(60 * i)),
                              r * math.sin(math.radians(60 * i))) for i in range(6)])


class CoreRenderer:
    def __init__(self):
        self.angle = 0.0

    def advance(self, dt: float, spin: float) -> None:
        self.angle += dt * 30.0 * (0.5 + spin)

    def paint(self, p: QPainter, c: QPointF, core_r: float, R: float,
              col: QColor, jitter: float, pulse: float) -> None:
        self._halo(p, c, R, col)
        self._lattice(p, c, core_r, col)
        self._shells(p, c, core_r, col, jitter)
        self._streak(p, c, R, col, pulse)
        self._centre(p, c, core_r, col)

    def _halo(self, p, c, R, col):
        g = QRadialGradient(c, R * 0.6)
        g.setColorAt(0.0, rgba(col, 95))
        g.setColorAt(0.5, rgba(col, 28))
        g.setColorAt(1.0, rgba(col, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(c, R * 0.6, R * 0.6)

    def _lattice(self, p, c, core_r, col):
        p.save()
        p.translate(c)
        for rad, rot, alpha in ((2.5, self.angle, 120), (1.8, -self.angle * 1.4, 90)):
            p.save()
            p.rotate(rot)
            poly = _hexagon(core_r * rad)
            p.setPen(QPen(rgba(col, alpha), 1.1))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(poly)
            p.setPen(QPen(rgba(col, 28), 0.8))
            for v in poly:
                p.drawLine(QPointF(0, 0), v)
            p.restore()
        p.restore()

    def _shells(self, p, c, core_r, col, jitter):
        for k in range(3):
            off = jitter * core_r * 0.18 * (k - 1)
            p.setPen(QPen(rgba(col, 150 - k * 35), 1.4))
            p.setBrush(Qt.NoBrush)
            rr = core_r * (1.0 + 0.18 * k)
            p.drawEllipse(QPointF(c.x() + off, c.y() - off * 0.6), rr, rr)

    def _streak(self, p, c, R, col, pulse):
        half = R * (0.55 + 0.3 * pulse)
        g = QLinearGradient(c.x() - half, 0, c.x() + half, 0)
        g.setColorAt(0.0, rgba(col, 0))
        g.setColorAt(0.5, rgba(col, 110))
        g.setColorAt(1.0, rgba(col, 0))
        p.setPen(QPen(QBrush(g), 1))
        p.drawLine(QPointF(c.x() - half, c.y()), QPointF(c.x() + half, c.y()))

    def _centre(self, p, c, core_r, col):
        g = QRadialGradient(c, core_r)
        g.setColorAt(0.0, QColor(255, 255, 255, 255))
        g.setColorAt(0.35, rgba(col, 235))
        g.setColorAt(1.0, rgba(col, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(c, core_r, core_r)
