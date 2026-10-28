"""Left-hand telemetry column: live values with sparklines."""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .states import StateModel
from .theme import THEME, rgba

# name -> (unit, decimals)
METRICS = {
    "Latency":       ("ms", 0),
    "Throughput":    ("tok/s", 1),
    "Memory nodes":  ("", 0),
    "Skills":        ("", 0),
}


class TelemetryPanel(QWidget):
    ROW_H = 86

    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.setFixedWidth(210)
        self.setFixedHeight(self.ROW_H * len(METRICS))
        self._data = {k: deque([0.0] * 40, maxlen=40) for k in METRICS}
        self._seeded: set[str] = set()
        model.ticked.connect(self._on_tick)

    def _on_tick(self, _dt: float) -> None:
        self.update()

    def push(self, name: str, value: float) -> None:
        if name not in self._data:
            return
        if name not in self._seeded:  # first sample: fill history so the graph starts flat, not spiked
            self._data[name].extend([float(value)] * self._data[name].maxlen)
            self._seeded.add(name)
        self._data[name].append(float(value))

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = self.model.style.color
        w = self.width()
        small = QFont(THEME.font, 9)
        big = QFont(THEME.mono, 20)
        big.setWeight(QFont.Light)

        for idx, (name, (unit, dec)) in enumerate(METRICS.items()):
            top = idx * self.ROW_H
            hist = self._data[name]
            ip = self.model.intro.p(0.6 + 0.12 * idx, 0.7)
            if ip <= 0:
                continue
            p.save()
            p.setOpacity(ip)
            p.translate(-(1 - ip) * 30, 0)

            bracket = QLinearGradient(0, top, 0, top + self.ROW_H - 12)
            bracket.setColorAt(0.0, rgba(col, 160))
            bracket.setColorAt(1.0, rgba(col, 0))
            p.setPen(QPen(bracket, 1.4))
            p.drawLine(0, top + 6, 0, top + self.ROW_H - 12)

            p.setFont(small)
            p.setPen(rgba(THEME.dim, 255))
            p.drawText(QPointF(14, top + 18), name)

            p.setFont(big)
            p.setPen(rgba(THEME.text, 255))
            txt = f"{hist[-1]:.{dec}f}"
            p.drawText(QPointF(14, top + 46), txt)
            if unit:
                adv = p.fontMetrics().horizontalAdvance(txt)
                p.setFont(small)
                p.setPen(rgba(THEME.dim, 255))
                p.drawText(QPointF(14 + adv + 6, top + 46), unit)

            p.save()
            p.setClipRect(QRectF(0, top + 48, (w + 4) * ip, 34))
            self._spark(p, hist, 14, top + 54, w - 20, 20, col)
            p.restore()
            p.restore()

    @staticmethod
    def _spark(p: QPainter, hist, x: float, y: float, w: float, h: float, col) -> None:
        lo, hi = min(hist), max(hist)
        if hi - lo < 1e-6:
            hi = lo + 1.0
        n = len(hist)
        pts = [QPointF(x + w * i / (n - 1), y + h - h * (v - lo) / (hi - lo)) for i, v in enumerate(hist)]
        line = QPainterPath(pts[0])
        for pt in pts[1:]:
            line.lineTo(pt)
        area = QPainterPath(line)
        area.lineTo(x + w, y + h)
        area.lineTo(x, y + h)
        area.closeSubpath()
        fill = QLinearGradient(0, y, 0, y + h)
        fill.setColorAt(0.0, rgba(col, 60))
        fill.setColorAt(1.0, rgba(col, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawPath(area)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(rgba(col, 210), 1.2))
        p.drawPath(line)
