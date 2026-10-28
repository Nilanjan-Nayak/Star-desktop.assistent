"""Turns folder names the user typed ("Nilanjan folder") into real absolute paths, or into a question."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from ..security import PermissionPolicy

LOCATION_SUFFIXES = ("_dir", "_path", "_folder", "dir", "path", "folder", "root", "location", "destination")
_SKIP = {".git", "node_modules", "__pycache__", "$recycle.bin", "system volume information", "appdata", "windows"}


def is_location_key(key: str) -> bool:
    k = key.lower()
    return k in LOCATION_SUFFIXES or any(k.endswith(s) for s in LOCATION_SUFFIXES) or any(s in k for s in ("folder", "dir", "path"))


def is_dest_key(key: str) -> bool:
    return key.startswith(("dest", "target", "output", "to_"))


def tr(lang: str, bn: str, banglish: str, en: str) -> str:
    return {"bn": bn, "banglish": banglish}.get(lang, en)


@dataclass
class Resolved:
    path: Path | None = None
    question: str | None = None
    error: str | None = None      # hard refusal (outside allowed folders): not a question


def _find_dirs(name: str, roots: list[Path], max_depth: int = 4, limit: int = 8000) -> list[Path]:
    found, seen = [], 0
    target = name.lower()
    for root in roots:
        if not root.is_dir():
            continue
        base_depth = len(root.parts)
        for cur, dirs, _files in os.walk(root):
            depth = len(Path(cur).parts) - base_depth
            dirs[:] = [d for d in dirs if d.lower() not in _SKIP and not d.startswith(".")] if depth < max_depth else []
            seen += 1
            if Path(cur).name.lower() == target:
                found.append(Path(cur))
            if seen > limit:
                break
    return sorted(set(found))


def resolve_location(raw: str, key: str, policy: PermissionPolicy, lang: str) -> Resolved:
    raw = raw.strip().strip("\"'")
    if os.name == "nt" and raw.startswith("/") and not raw.startswith("//"):
        return Resolved(error=tr(lang, f"'{raw}' আমার অনুমোদিত ফোল্ডারের বাইরে, তাই ওখানে কাজ করব না।",
                                 f"'{raw}' amar allowed folder er baire, tai okhane kaj korbo na.",
                                 f"'{raw}' is outside the folders I'm allowed to use, so I won't touch it."))
    p = Path(raw).expanduser()
    looks_abs = p.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", raw) is not None
    if looks_abs:
        if not p.is_absolute():  # a Windows path while running elsewhere: cannot be checked here
            return Resolved(error=tr(lang, f"এই পাথ চেনা যাচ্ছে না: {raw}", f"Ei path chena jachhe na: {raw}",
                                     f"Cannot use this path here: {raw}"))
        if not policy.is_allowed(p):
            return Resolved(error=tr(lang, f"'{raw}' আমার অনুমোদিত ফোল্ডারের বাইরে, তাই ওখানে কাজ করব না।",
                                     f"'{raw}' amar allowed folder er baire, tai okhane kaj korbo na.",
                                     f"'{raw}' is outside the folders I'm allowed to use, so I won't touch it."))
        rp = p.resolve()
        if rp.is_dir() or is_dest_key(key):
            return Resolved(path=rp)
        return Resolved(question=tr(lang, f"'{raw}' ফোল্ডারটা পাইনি। সঠিক পাথ কী?", f"'{raw}' folder ta pai ni. Sothik path ki?",
                                    f"I can't find the folder '{raw}'. What is the correct path?"))
    clean_name = re.sub(r"^(the|my)\s+", "", raw.strip(), flags=re.I)
    clean_name = re.sub(r"\s+(folder|directory|dir)$", "", clean_name, flags=re.I).strip()
    for r in policy.roots:
        if r.name.lower() in (raw.lower(), clean_name.lower()):
            return Resolved(path=r.resolve())

    cands = _find_dirs(raw, policy.roots)
    if len(cands) == 1:
        return Resolved(path=cands[0])
    if len(cands) > 1:
        root_match = [c for c in cands if any(c.resolve() == r.resolve() for r in policy.roots)]
        if len(root_match) == 1:
            return Resolved(path=root_match[0])
        shown = "; ".join(str(c) for c in cands[:4])
        return Resolved(question=tr(lang, f"'{raw}' নামে একাধিক ফোল্ডার আছে: {shown}। কোনটি?",
                                    f"'{raw}' naame ekadhik folder ache: {shown}. Konta?",
                                    f"Several folders are named '{raw}': {shown}. Which one?"))
    if is_dest_key(key):
        where = ", ".join(str(r) for r in policy.roots[:2])
        return Resolved(question=tr(lang, f"'{raw}' ফোল্ডার কোথায় তৈরি করব? (পূর্ণ পাথ দাও, যেমন {where}\\{raw})",
                                    f"'{raw}' folder kothay toiri korbo? (full path dao, jemon {where}\\{raw})",
                                    f"Where should I create '{raw}'? (give a full path, e.g. {where}\\{raw})"))
    return Resolved(question=tr(lang, f"'{raw}' ফোল্ডারটা অনুমোদিত জায়গায় খুঁজে পাইনি। পূর্ণ পাথ কী?",
                                f"'{raw}' folder ta allowed jaygay khuje pai ni. Full path ki?",
                                f"I couldn't find '{raw}' in the allowed folders. What is the full path?"))
