"""Motion primitives: springs, easings and the boot-sequence timeline.

Everything animated in the UI runs off the single StateModel clock, so motion is
frame-synced and cheap. Springs are used wherever something has to *follow* a moving
target (layout, tabs); easings are used for fixed-length entrances.
"""
from __future__ import annotations

import math


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def ease_out_back(t: float, s: float = 1.70158) -> float:
    """Overshoots slightly past 1, then settles: good for pop-ins."""
    t = clamp01(t) - 1
    return t * t * ((s + 1) * t + s) + 1


class Spring:
    """Damped spring toward `target`. Critically damped by default (no overshoot)."""

    __slots__ = ("x", "v", "target", "k", "c")

    def __init__(self, value: float = 0.0, k: float = 220.0, c: float | None = None):
        self.x = value
        self.v = 0.0
        self.target = value
        self.k = k
        self.c = 2.0 * math.sqrt(k) if c is None else c

    @classmethod
    def bouncy(cls, value: float = 0.0, k: float = 300.0) -> "Spring":
        return cls(value, k, 0.62 * 2.0 * math.sqrt(k))

    def snap(self, value: float | None = None) -> None:
        if value is not None:
            self.target = value
        self.x, self.v = self.target, 0.0

    def update(self, dt: float) -> float:
        steps = max(1, int(dt / 0.008))
        h = dt / steps
        for _ in range(steps):
            self.v += (self.k * (self.target - self.x) - self.c * self.v) * h
            self.x += self.v * h
        return self.x

    @property
    def settled(self) -> bool:
        return abs(self.target - self.x) < 0.05 and abs(self.v) < 0.05


class Intro:
    """Boot timeline. `p(delay, duration)` is eased 0..1 progress of one element's entrance."""

    def __init__(self, model):
        self._model = model
        self._t0: float | None = None

    def start(self) -> None:
        self._t0 = self._model.time

    def reset(self) -> None:
        self._t0 = None

    @property
    def started(self) -> bool:
        return self._t0 is not None

    def elapsed(self) -> float:
        return 0.0 if self._t0 is None else self._model.time - self._t0

    def p(self, delay: float, duration: float, ease=ease_out_cubic) -> float:
        if self._t0 is None:
            return 0.0
        return ease((self._model.time - self._t0 - delay) / duration)
