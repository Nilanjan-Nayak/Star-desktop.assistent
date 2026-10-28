"""Segmented HUD rings, tick dial and rotating marker around the reactor."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from .theme import rgba


class OrbitRings:
    def __init__(self):
        # f: radius fraction, w: pen width, dir: spin direction, k: speed factor
        self._rings = [
            dict(f=0.54, w=1.4, dir=1,  k=1.0, a=0.0,   segs=[(0, 70), (110, 40), (200, 90), (310, 25)]),
            dict(f=0.72, w=2.4, dir=-1, k=0.6, a=40.0,  segs=[(20, 100), (160, 60), (250, 70)]),
            dict(f=0.86, w=1.0, dir=1,  k=0.35, a=10.0, segs=[(0, 30), (90, 30), (180, 30), (270, 30)]),
        ]
        self._dial = 0.0

    def advance(self, dt: float, speed: float) -> None:
        for r in self._rings:
            r["a"] += r["dir"] * r["k"] * speed * dt * 40.0
        self._dial += dt * speed * 3.0

    def paint(self, p: QPainter, c: QPointF, R: float, col: QColor, grow: float = 1.0) -> None:
        if grow <= 0:
            return
        p.setBrush(Qt.NoBrush)
        for i, r in enumerate(self._rings):
            rr = R * r["f"]
            rect = QRectF(c.x() - rr, c.y() - rr, rr * 2, rr * 2)
            pen = QPen(rgba(col, (150 - i * 30) * grow), r["w"])
            pen.setCapStyle(Qt.FlatCap)
            p.setPen(pen)
            for start, span in r["segs"]:
                p.drawArc(rect, int(((start + r["a"]) % 360) * 16), int(span * grow * 16))
        if grow > 0.7:
            self._marker(p, c, R)
        self._dial_ticks(p, c, R, col, grow)

    def _marker(self, p: QPainter, c: QPointF, R: float) -> None:
        r = self._rings[1]
        ang = math.radians(r["a"])
        rr = R * r["f"] + 7
        tip = QPointF(c.x() + rr * math.cos(ang), c.y() - rr * math.sin(ang))
        nx, ny = math.cos(ang), -math.sin(ang)
        tx, ty = -ny, nx
        tri = QPolygonF([tip,
                         QPointF(tip.x() + 7 * nx + 4 * tx, tip.y() + 7 * ny + 4 * ty),
                         QPointF(tip.x() + 7 * nx - 4 * tx, tip.y() + 7 * ny - 4 * ty)])
        p.setPen(Qt.NoPen)
        p.setBrush(rgba("#ffffff", 200))
        p.drawPolygon(tri)

    def _dial_ticks(self, p: QPainter, c: QPointF, R: float, col: QColor, grow: float = 1.0) -> None:
        n = 90
        p.save()
        p.translate(c)
        p.rotate(math.degrees(self._dial) * 0.2)
        for i in range(n):
            long = i % 5 == 0
            if i / n > grow:  # dial draws itself clockwise
                break
            p.setPen(QPen(rgba(col, 140 if long else 55), 1))
            r0 = R * 0.98
            p.drawLine(QPointF(r0, 0), QPointF(r0 + (R * 0.035 if long else R * 0.018), 0))
            p.rotate(360 / n)
        p.restore()
