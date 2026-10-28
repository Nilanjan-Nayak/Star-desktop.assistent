"""One-shot creation effects for ordinary widgets: fades, staggers, scramble-decode text, typing."""
from __future__ import annotations

import random

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QLineEdit, QWidget

from .motion import clamp01


def fade_in(widget: QWidget, delay: float = 0.0, duration: float = 0.4) -> None:
    """Fade a widget in after `delay` seconds. Skips widgets that already own an effect."""
    if widget.graphicsEffect() is not None:
        return
    fx = QGraphicsOpacityEffect(widget)
    fx.setOpacity(0.0)
    widget.setGraphicsEffect(fx)
    anim = QPropertyAnimation(fx, b"opacity", widget)
    anim.setDuration(int(duration * 1000))
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.finished.connect(lambda w=widget, e=fx: w.setGraphicsEffect(None) if w.graphicsEffect() is e else None)
    timer = QTimer(widget)  # owned by the widget: dies with it, so no dangling callbacks
    timer.setSingleShot(True)
    timer.timeout.connect(anim.start)
    timer.start(int(delay * 1000))


def stagger(widgets, start: float = 0.0, step: float = 0.07, duration: float = 0.4) -> None:
    for i, w in enumerate(widgets):
        fade_in(w, start + i * step, duration)


class ScrambleLabel(QLabel):
    """Text that decodes from random glyphs into its final value, left to right."""

    GLYPHS = "01<>/\\[]{}#%&*+=?"

    def __init__(self, parent: QWidget | None = None):
        super().__init__("", parent)
        self._target, self._t, self._dur = "", 0.0, 0.6
        self._rng = random.Random()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._step)

    def reveal(self, text: str, duration: float = 0.6, delay: float = 0.0) -> None:
        self._target, self._dur, self._t = text, max(0.05, duration), -delay
        self.setText("\u00a0" * len(text))  # reserve the final width/height immediately
        self._timer.start()

    def _step(self) -> None:
        self._t += 0.033
        if self._t < 0:
            return
        prog = clamp01(self._t / self._dur)
        n = int(prog * len(self._target))
        tail = "".join(c if c == " " else self._rng.choice(self.GLYPHS) for c in self._target[n:])
        self.setText(self._target[:n] + tail)
        if prog >= 1.0:
            self.setText(self._target)
            self._timer.stop()


def type_into(edit: QLineEdit, text: str, duration: float = 0.6, delay: float = 0.0) -> None:
    """Type `text` into a line edit character by character."""
    state = {"t": -delay}
    timer = QTimer(edit)
    timer.setInterval(30)

    def step() -> None:
        state["t"] += 0.03
        if state["t"] < 0:
            return
        prog = clamp01(state["t"] / max(0.05, duration))
        edit.setText(text[: int(prog * len(text))] + ("" if prog >= 1 else "\u258d"))
        if prog >= 1:
            edit.setText(text)
            timer.stop()

    timer.timeout.connect(step)
    timer.start()
