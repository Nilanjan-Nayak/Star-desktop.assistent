"""Orbiting particle field with proximity energy lines."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from .theme import rgba


class Particle:
    __slots__ = ("ring", "angle", "speed", "size", "phase", "depth")

    def __init__(self, rnd: random.Random):
        self.ring = 0.22 + 0.78 * math.sqrt(rnd.random())
        self.angle = rnd.random() * math.tau
        self.speed = (0.25 + rnd.random() * 0.5) * rnd.choice((-1, 1))
        self.depth = rnd.random()
        self.size = 1.0 + rnd.random() * 2.0
        self.phase = rnd.random() * math.tau


class ParticleField:
    def __init__(self, count: int = 52, seed: int = 7):
        rnd = random.Random(seed)
        self.items = [Particle(rnd) for _ in range(count)]

    def advance(self, dt: float, spin: float) -> None:
        for p in self.items:
            p.angle += p.speed * spin * dt

    def positions(self, c: QPointF, r: float, t: float):
        out = []
        for pt in self.items:
            rr = r * pt.ring * (1 + 0.04 * math.sin(t * 0.9 + pt.phase))
            out.append((QPointF(c.x() + rr * math.cos(pt.angle),
                                c.y() + rr * 0.92 * math.sin(pt.angle)), pt))
        return out

    @staticmethod
    def draw_links(p: QPainter, pts, max_d: float, col: QColor) -> None:
        pen = QPen()
        pen.setWidthF(0.8)
        for i in range(len(pts)):
            a = pts[i][0]
            for j in range(i + 1, len(pts)):
                b = pts[j][0]
                d = math.hypot(a.x() - b.x(), a.y() - b.y())
                if d < max_d:
                    pen.setColor(rgba(col, 120 * (1 - d / max_d) ** 1.5))
                    p.setPen(pen)
                    p.drawLine(a, b)

    @staticmethod
    def draw_nodes(p: QPainter, pts, t: float, col: QColor) -> None:
        p.setPen(Qt.NoPen)
        for pos, pt in pts:
            tw = 0.55 + 0.45 * math.sin(t * 3 + pt.phase)
            size = pt.size * (0.7 + 0.6 * pt.depth)
            p.setBrush(rgba(col, (50 + 170 * tw) * (0.5 + 0.5 * pt.depth)))
            p.drawEllipse(pos, size, size)
