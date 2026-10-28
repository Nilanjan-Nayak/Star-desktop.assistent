"""Stage: absolute-positioned container that glides its children to new arrangements.

Qt layouts snap. Stage keeps one spring per edge of every child, so when the window
resizes, a breakpoint flips, or the terminal opens, elements slide and resize smoothly.
Hidden elements exit by sliding and fading rather than vanishing.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Signal
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from .motion import Spring
from .states import StateModel


class _Slot:
    def __init__(self, widget: QWidget, exit_offset, scale_in: float, collapse: bool, opacity_cb):
        self.widget = widget
        self.exit = exit_offset
        self.scale_in = scale_in
        self.collapse = collapse          # exit by shrinking toward the right edge (terminal)
        self.opacity_cb = opacity_cb      # custom opacity setter, else a managed effect
        self.x, self.y = Spring(0, 200), Spring(0, 200)
        self.w, self.h = Spring(0, 200), Spring(0, 200)
        self.o = Spring(0, 240)
        self.placed = False
        self.visible = False
        self.rect: QRectF | None = None   # last visible target
        self.fx: QGraphicsOpacityEffect | None = None


class Stage(QWidget):
    resized = Signal()

    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self._slots: dict[str, _Slot] = {}
        self._targets: dict[str, QRectF | None] = {}
        model.ticked.connect(self._tick)

    def add(self, name: str, widget: QWidget, exit_offset=(0.0, 0.0), scale_in: float = 1.0,
            collapse: bool = False, opacity_cb=None) -> None:
        widget.setParent(self)
        widget.hide()
        self._slots[name] = _Slot(widget, exit_offset, scale_in, collapse, opacity_cb)

    # arrangement ---------------------------------------------------------------------
    def _hidden_rect(self, s: _Slot, r: QRectF) -> QRectF:
        if s.collapse:
            return QRectF(self.width(), r.y(), 0.0, r.height())
        dx, dy = s.exit
        w, h = r.width() * s.scale_in, r.height() * s.scale_in
        return QRectF(r.center().x() - w / 2 + dx, r.center().y() - h / 2 + dy, w, h)

    @staticmethod
    def _aim(s: _Slot, r: QRectF) -> None:
        s.x.target, s.y.target, s.w.target, s.h.target = r.x(), r.y(), r.width(), r.height()

    def arrange(self, targets: dict, snap: bool = False) -> None:
        self._targets = dict(targets)
        for name, s in self._slots.items():
            r = targets.get(name)
            if r is not None:
                if not s.placed or snap:
                    start = r if snap else self._hidden_rect(s, r)
                    for sp, v in ((s.x, start.x()), (s.y, start.y()), (s.w, start.width()), (s.h, start.height())):
                        sp.snap(v)
                    s.o.snap(1.0 if snap else 0.0)
                    s.placed = True
                s.rect, s.visible = r, True
                self._aim(s, r)
                s.o.target = 1.0
            elif s.placed and s.rect is not None:
                s.visible = False
                self._aim(s, self._hidden_rect(s, s.rect))
                s.o.target = 0.0 if not s.collapse else 1.0

    def replay(self) -> None:
        """Unplace everything so the next arrange() plays the creation animation again."""
        for s in self._slots.values():
            s.placed = False
            s.widget.hide()
        self.arrange(self._targets)

    # per-frame ------------------------------------------------------------------------
    def _tick(self, dt: float) -> None:
        for s in self._slots.values():
            if not s.placed:
                continue
            for sp in (s.x, s.y, s.w, s.h, s.o):
                sp.update(dt)
            w = s.widget
            rect = QRect(round(s.x.x), round(s.y.x), max(0, round(s.w.x)), max(0, round(s.h.x)))
            if s.collapse:
                show = s.visible or s.w.x > 8
            else:
                show = s.visible or s.o.x > 0.01
            if not show:
                if w.isVisible():
                    w.hide()
                continue
            if w.geometry() != rect:
                w.setGeometry(rect)
            if not w.isVisible():
                w.show()
            if not s.collapse:
                self._apply_opacity(s)

    @staticmethod
    def _apply_opacity(s: _Slot) -> None:
        o = max(0.0, min(1.0, s.o.x))
        if s.opacity_cb is not None:
            s.opacity_cb(o)
            return
        if o >= 0.995 and s.visible and s.o.settled:
            if s.fx is not None:
                s.widget.setGraphicsEffect(None)
                s.fx = None
            return
        if s.fx is None:
            s.fx = QGraphicsOpacityEffect(s.widget)
            s.widget.setGraphicsEffect(s.fx)
        s.fx.setOpacity(o)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self.resized.emit()
