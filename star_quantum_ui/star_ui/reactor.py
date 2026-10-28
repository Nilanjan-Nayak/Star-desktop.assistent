"""QuantumReactor: composes rings, particle field and core; adds state-change ripples."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from .core import CoreRenderer
from .motion import ease_out_back
from .particles import ParticleField
from .rings import OrbitRings
from .states import StateModel
from .theme import rgba

RIPPLE_LIFE = 1.4  # seconds


class QuantumReactor(QWidget):
    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.setMinimumSize(220, 220)
        self._particles = ParticleField()
        self._rings = OrbitRings()
        self._core = CoreRenderer()
        self._ripples: list[float] = []
        model.ticked.connect(self._on_tick)
        model.changed.connect(lambda _n: self._ripples.append(self.model.time))

    def _on_tick(self, dt: float) -> None:
        s = self.model.style
        self._particles.advance(dt, s.spin)
        self._rings.advance(dt, s.ring_speed)
        self._core.advance(dt, s.spin)
        t = self.model.time
        self._ripples = [b for b in self._ripples if t - b < RIPPLE_LIFE]
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        s, t = self.model.style, self.model.time
        intro = self.model.intro
        ip = intro.p(0.25, 1.5)
        if ip <= 0:
            return
        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)
        R = min(w, h) * 0.46
        col = s.color

        breath = 1 + s.pulse * math.sin(t * math.tau * s.pulse_hz)
        jitter = s.flicker * (0.5 * math.sin(t * 23.0) + 0.3 * math.sin(t * 41.0 + 1.3)
                              + 0.2 * math.sin(t * 67.0 + 2.1))
        core_p = max(0.0, ease_out_back(intro.p(0.2, 0.9)))
        core_r = R * 0.15 * breath * (1 + 0.12 * jitter) * core_p
        part_p = intro.p(0.55, 1.3)

        p.translate(c)
        p.rotate(-60 * (1 - ip))
        sc = 0.6 + 0.4 * ip
        p.scale(sc, sc)
        p.translate(-c)
        p.setOpacity(min(1.0, ip * 1.8))

        self._rings.paint(p, c, R, col, intro.p(0.45, 1.2))
        pts = self._particles.positions(c, R * (0.15 + 0.85 * part_p), t)
        self._particles.draw_links(p, pts, R * s.link * part_p, col)
        self._particles.draw_nodes(p, pts, t, col)
        self._core.paint(p, c, core_r, R, col, jitter, s.pulse)
        self._ripple_layer(p, c, R, col, t)

    def _ripple_layer(self, p: QPainter, c: QPointF, R: float, col, t: float) -> None:
        p.setBrush(Qt.NoBrush)
        for birth in self._ripples:
            f = (t - birth) / RIPPLE_LIFE
            ease = 1 - (1 - f) ** 3
            rad = R * (0.2 + 0.9 * ease)
            p.setPen(QPen(rgba(col, 170 * (1 - f) ** 2), 2.0))
            p.drawEllipse(c, rad, rad)
