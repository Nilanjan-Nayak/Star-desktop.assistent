"""Workflow skills: a successful plan turned into a reusable template with named parameters."""
from __future__ import annotations

from ..brain.resolver import is_location_key
from ..models import Plan, Step

MARK = "<<{}>>"


def _walk(value, fn):
    if isinstance(value, str):
        return fn(value)  # fn may return a non-str (a typed parameter value)
    if isinstance(value, list):
        return [_walk(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: _walk(v, fn) for k, v in value.items()}
    return value


def generalize(steps: list[Step], entities: dict) -> tuple[list[dict], list[str]]:
    """Replace concrete values that came from the user's request with <<param>> markers."""
    mapping = {str(v): k for k, v in entities.items() if isinstance(v, (str, int)) and not isinstance(v, bool) and str(v)}
    used: list[str] = []

    def sub(s: str) -> str:
        if s in mapping:
            used.append(mapping[s])
            return MARK.format(mapping[s])
        for val, key in mapping.items():
            if is_location_key(key) and (s.startswith(val + "/") or s.startswith(val + "\\")):
                used.append(key)
                return MARK.format(key) + s[len(val):]
        return s

    out = [{"id": s.id, "tool": s.tool, "args": _walk(s.args, sub), "description": s.description} for s in steps]
    return out, list(dict.fromkeys(used))


def bind(template: list[dict], params: dict) -> list[Step]:
    """Fill the markers. A value that is exactly one marker keeps the parameter's own type."""
    def sub(s: str):
        for k, v in params.items():
            m = MARK.format(k)
            if s == m:
                return v
            if m in s:
                s = s.replace(m, str(v))
        if "<<" in s and ">>" in s:
            raise KeyError(f"unbound parameter in {s!r}")
        return s

    return [Step(t["id"], t["tool"], _walk(t["args"], sub) if not isinstance(t["args"], str) else sub(t["args"]),
                 t.get("description", "")) for t in template]
