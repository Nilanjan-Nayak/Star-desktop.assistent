"""Vector icons drawn with QPainter, so they take any colour and scale cleanly."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF


def draw_icon(p: QPainter, name: str, r: QRectF, color: QColor, width: float = 1.5) -> None:
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    c = r.center()
    s = min(r.width(), r.height()) / 2
    cx, cy = c.x(), c.y()

    def line(x1, y1, x2, y2):
        p.drawLine(QPointF(cx + x1 * s, cy + y1 * s), QPointF(cx + x2 * s, cy + y2 * s))

    def poly(pts, fill=False):
        if fill:
            p.setBrush(color)
        p.drawPolygon(QPolygonF([QPointF(cx + x * s, cy + y * s) for x, y in pts]))

    if name == "web":
        p.drawEllipse(c, s, s)
        p.drawEllipse(c, s * 0.42, s)
        line(-1, 0, 1, 0)
    elif name == "agent":
        poly([(0.2, -1), (-0.65, 0.15), (-0.05, 0.15), (-0.2, 1), (0.65, -0.2), (0.05, -0.2)])
    elif name == "system":
        p.drawRoundedRect(QRectF(cx - s * 0.58, cy - s * 0.58, s * 1.16, s * 1.16), 2, 2)
        for k in (-0.3, 0.3):
            line(k, -0.58, k, -1)
            line(k, 0.58, k, 1)
            line(-0.58, k, -1, k)
            line(0.58, k, 1, k)
    elif name == "close":
        line(-0.6, -0.6, 0.6, 0.6)
        line(0.6, -0.6, -0.6, 0.6)
    elif name == "minimize":
        line(-0.7, 0.3, 0.7, 0.3)
    elif name == "back":
        line(0.3, -0.7, -0.4, 0)
        line(-0.4, 0, 0.3, 0.7)
    elif name == "forward":
        line(-0.3, -0.7, 0.4, 0)
        line(0.4, 0, -0.3, 0.7)
    elif name == "reload":
        p.drawArc(QRectF(cx - s * 0.75, cy - s * 0.75, s * 1.5, s * 1.5), 80 * 16, 280 * 16)
        line(0.1, -1.0, 0.45, -0.7)
        line(0.1, -1.0, 0.45, -1.25)
    elif name == "play":
        poly([(-0.5, -0.75), (0.75, 0), (-0.5, 0.75)], fill=True)
    elif name == "pause":
        line(-0.35, -0.7, -0.35, 0.7)
        line(0.35, -0.7, 0.35, 0.7)
    elif name == "stop":
        p.setBrush(color)
        p.drawRoundedRect(QRectF(cx - s * 0.55, cy - s * 0.55, s * 1.1, s * 1.1), 2, 2)
    elif name == "check":
        line(-0.7, 0.05, -0.2, 0.55)
        line(-0.2, 0.55, 0.75, -0.55)
    elif name == "send":
        poly([(-0.8, -0.7), (0.85, 0), (-0.8, 0.7), (-0.45, 0)])
    p.restore()
