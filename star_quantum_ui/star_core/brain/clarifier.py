"""Socratic Clarification Protocol (Section 7).

Detects ambiguous, underspecified or vague user instructions:
- Complex tasks with queries < 5 words
- Vague pronouns without clear antecedent ('oita', 'eta', 'sheta', 'this', 'that')
- Missing critical parameters (theme, scope, type)
Generates 2-3 structured clarification options rather than guessing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ClarificationRequest:
    needed: bool
    question: str | None = None
    options: list[str] | None = None


VAGUE_PRONOUNS = ("oita", "eita", "eta", "sheta", "this", "that")
COMPLEX_TARGETS = ("website", "web page", "web site", "app", "game", "portfolio", "dashboard", "system")


class SocraticClarifier:
    def check_query(self, query: str, intent: str = "") -> ClarificationRequest:
        words = query.strip().split()
        low = query.lower().strip()

        # Rule 1: Vague pronoun detection
        if len(words) <= 3 and any(p in words for p in VAGUE_PRONOUNS):
            pronoun = next(p for p in words if p in VAGUE_PRONOUNS)
            return ClarificationRequest(
                needed=True,
                question=f"🤔 '{pronoun.capitalize()}' bolte specifically ki bujhaccho? Detail e bolle ami shothik bhabe execute korte parbo.",
                options=["Specific file or action name dao", "Ager kaj ta continue koro"],
            )

        # Rule 2: Short underspecified complex requests
        if len(words) <= 4 and any(t in low for t in COMPLEX_TARGETS):
            if "website" in low or "portfolio" in low:
                q = (
                    "🤔 Kaj ta prothom thekei professional korte 2-3 ti details dorkar:\n"
                    "1. Ki dhoroner website? (Portfolio | Business | Landing Page)\n"
                    "2. Theme ki hobe? (Dark | Light | Minimalist)\n"
                    "3. Koyti section ba page lagbe? (1 | 3 | 5+)\n"
                    "💬 Ekti choto uttor dile ami shera design toiri kore debo!"
                )
                return ClarificationRequest(
                    needed=True,
                    question=q,
                    options=["Dark Theme Portfolio", "Light Modern Landing Page", "Minimalist Blog"],
                )
            elif "app" in low or "game" in low:
                q = (
                    "🤔 App/Game toiri korar age kichu details janale bhalo hoy:\n"
                    "1. Kon language e banabo? (Python Tkinter/Pygame | Web HTML/JS)\n"
                    "2. Core feature ki thakbe?\n"
                    "💬 Short answer dao, ami shuru korchi!"
                )
                return ClarificationRequest(
                    needed=True,
                    question=q,
                    options=["Web HTML/JS App", "Python Desktop GUI", "CLI Script"],
                )

        return ClarificationRequest(needed=False)
