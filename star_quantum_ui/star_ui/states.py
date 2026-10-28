"""Assistant states and the single shared animation clock.

StateModel owns ONE timer for the whole UI. Every widget connects to `ticked`
and reads the smoothly blended `style`, so all elements stay in sync and
state changes ease in instead of snapping.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor

from .motion import Intro
from .theme import THEME, lerp, mix


@dataclass(frozen=True)
class StateStyle:
    label: str
    color: str
    spin: float        # particle orbit speed
    flicker: float     # core instability 0..1
    link: float        # energy-line reach (fraction of radius)
    pulse: float       # core breathing amplitude
    pulse_hz: float
    ring_speed: float  # HUD ring rotation
    wave_amp: float    # waveform height 0..1


STATES: dict[str, StateStyle] = {
    "idle":      StateStyle("Standing by", THEME.cyan,   0.35, 0.10, 0.28, 0.03, 0.25, 0.25, 0.06),
    "listening": StateStyle("Listening",   THEME.violet, 0.60, 0.25, 0.34, 0.07, 0.80, 0.60, 0.45),
    "thinking":  StateStyle("Thinking",    THEME.cyan,   2.10, 0.65, 0.46, 0.05, 2.20, 2.40, 0.22),
    "speaking":  StateStyle("Speaking",    THEME.amber,  1.00, 0.35, 0.36, 0.10, 3.40, 1.10, 0.85),
}

_NUMERIC = ("spin", "flicker", "link", "pulse", "pulse_hz", "ring_speed", "wave_amp")


class LiveStyle:
    """Mutable, smoothly interpolated copy of a StateStyle."""

    def __init__(self, s: StateStyle):
        self.label = s.label
        self.color = QColor(s.color)
        for n in _NUMERIC:
            setattr(self, n, getattr(s, n))

    def approach(self, target: StateStyle, k: float) -> None:
        self.label = target.label
        self.color = mix(self.color, QColor(target.color), k)
        for n in _NUMERIC:
            setattr(self, n, lerp(getattr(self, n), getattr(target, n), k))


class StateModel(QObject):
    changed = Signal(str)   # new state name
    ticked = Signal(float)  # dt seconds, ~60 Hz

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._name = "idle"
        self.style = LiveStyle(STATES["idle"])
        self.time = 0.0
        self.intro = Intro(self)
        self._clock = QElapsedTimer()
        self._clock.start()
        self._last = 0.0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @property
    def name(self) -> str:
        return self._name

    def set_state(self, name: str) -> None:
        if name in STATES and name != self._name:
            self._name = name
            self.changed.emit(name)

    def _tick(self) -> None:
        now = self._clock.elapsed() / 1000.0
        dt = min(now - self._last, 0.05)
        self._last = now
        self.time += dt
        self.style.approach(STATES[self._name], 1 - math.exp(-dt * 4.0))
        self.ticked.emit(dt)
