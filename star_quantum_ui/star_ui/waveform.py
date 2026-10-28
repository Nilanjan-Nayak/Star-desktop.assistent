"""Mirrored voice waveform. Procedural by default; feed real audio with set_level()."""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .states import StateModel
from .theme import rgba


class WaveformBar(QWidget):
    BARS = 72

    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.setFixedHeight(72)
        self._h = [0.0] * self.BARS
        self._level: float | None = None
        model.ticked.connect(self._on_tick)

    def set_level(self, level: float) -> None:
        """0..1 live amplitude (mic or TTS). Negative -> back to procedural motion."""
        self._level = None if level < 0 else max(0.0, min(1.0, level))

    def _on_tick(self, dt: float) -> None:
        t = self.model.time
        amp = self.model.style.wave_amp if self._level is None else 0.1 + 0.9 * self._level
        k = min(1.0, dt * 14)
        n = self.BARS
        for i in range(n):
            x = i / (n - 1)
            env = math.exp(-(((x - 0.5) / 0.30) ** 2))
            v = (0.5 + 0.5 * math.sin(t * 6 + i * 0.45)) * (0.5 + 0.5 * math.sin(t * 3.1 - i * 0.21 + 1.7))
            target = (0.05 + amp * v) * env
            self._h[i] += (target - self._h[i]) * k
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        col = self.model.style.color
        mid = h / 2
        step = w / self.BARS
        bw = step * 0.5

        base = QLinearGradient(0, 0, w, 0)
        base.setColorAt(0.0, rgba(col, 0))
        base.setColorAt(0.5, rgba(col, 70))
        base.setColorAt(1.0, rgba(col, 0))
        p.setPen(QPen(base, 1))
        p.drawLine(0, int(mid), w, int(mid))

        p.setPen(Qt.NoPen)
        mid_i = self.BARS / 2
        for i, v in enumerate(self._h):
            ip = self.model.intro.p(0.9 + 0.012 * abs(i - mid_i), 0.5)
            bh = max(2.0, v * (h - 6)) * ip
            x = i * step + (step - bw) / 2
            p.setBrush(rgba(col, 70 + 185 * min(1.0, v * 1.4)))
            p.drawRoundedRect(QRectF(x, mid - bh / 2, bw, bh), bw / 2, bw / 2)
