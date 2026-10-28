"""Responsive rules: which elements show at a given size, and where each one goes."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF


@dataclass(frozen=True)
class Plan:
    name: str
    margin: int
    telemetry: bool
    ghost: bool
    chips: bool
    reactor: bool
    waveform: bool
    terminal_width: int


WIDE_FROM = 1280
MEDIUM_FROM = 900
GHOST_MIN_WIDTH = 820
TEL_W, TEL_H = 210, 344
GHOST_W, GHOST_H = 340, 280
GAP = 24
REACTOR_MIN = 200


def plan_for(width: int, height: int, terminal_open: bool) -> Plan:
    tight = terminal_open and height < 700  # give the terminal the vertical space
    if width >= WIDE_FROM:
        return Plan("wide", 40, True, not terminal_open, True, True, not tight, min(int(width * 0.55), 900))
    if width >= MEDIUM_FROM:
        return Plan("medium", 32, False, not terminal_open, True, True, not tight, int(width * 0.62))
    margin = 20
    return Plan("compact", margin, False, (not terminal_open) and width >= GHOST_MIN_WIDTH, False,
                not terminal_open, not terminal_open, width - 2 * margin)


def arrange(plan: Plan, w: float, h: float, terminal_open: bool) -> dict:
    """Target rect (stage coordinates) per element, or None when it should be hidden."""
    out: dict[str, QRectF | None] = {"telemetry": None, "reactor": None, "ghost": None, "terminal": None}
    right, left = w, 0.0
    if terminal_open:
        tw = min(plan.terminal_width, w)
        out["terminal"] = QRectF(w - tw, 0, tw, h)
        right = w - tw - GAP
    elif plan.ghost:
        out["ghost"] = QRectF(w - GHOST_W, (h - GHOST_H) / 2, GHOST_W, GHOST_H)
        right = w - GHOST_W - GAP
    if plan.telemetry and h >= TEL_H:
        out["telemetry"] = QRectF(0, (h - TEL_H) / 2, TEL_W, TEL_H)
        left = TEL_W + GAP
    if plan.reactor and right - left >= REACTOR_MIN:
        out["reactor"] = QRectF(left, 0, right - left, h)
    return out
