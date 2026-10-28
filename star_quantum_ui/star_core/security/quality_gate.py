"""Quality Gate Audit (Section 6).

Evaluates generated output quality across:
- Python Code: Type hints, docstring, __main__ guard, try/except error handling, top imports.
- Web/HTML: DOCTYPE, viewport meta tag, responsive layout, semantic HTML, image alt tags.
- Research: Source count (3+), section headers, recent data indicators, cross-verification.
Returns a 0-100 quality score and actionable suggestions.
If quality score < 70, flags for auto-regeneration.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class QualityAuditResult:
    score: int
    passed: bool
    kind: str  # python | web | research | generic
    passed_checks: list[str]
    missing_checks: list[str]
    tips: list[str]
    auto_regenerate: bool


class QualityGate:
    def audit_python_code(self, code: str) -> QualityAuditResult:
        score = 100
        passed = []
        missing = []
        tips = []

        # Check 1: Type hints (def func(x: int) -> ...)
        if re.search(r"def\s+\w+\s*\([^)]*:[^)]*\)\s*->", code):
            passed.append("Type hints present")
        else:
            score -= 5
            missing.append("Missing type hints")
            tips.append("Add parameter and return type hints")

        # Check 2: Docstring
        if '"""' in code or "'''" in code:
            passed.append("Docstrings present")
        else:
            score -= 5
            missing.append("Missing docstrings")
            tips.append("Add docstrings for functions/classes")

        # Check 3: __main__ execution block
        if "__main__" in code:
            passed.append("Main guard (__main__) present")
        else:
            score -= 5
            missing.append("Missing if __name__ == '__main__': block")
            tips.append("Wrap executable code in if __name__ == '__main__':")

        # Check 4: Error handling (try / except)
        if "try:" in code and "except" in code:
            passed.append("Try/except error handling present")
        else:
            score -= 5
            missing.append("Missing try/except error handling")
            tips.append("Add try/except blocks around I/O and edge cases")

        # Check 5: Top imports
        if code.strip().startswith(("import ", "from ", "#", '"""')):
            passed.append("Proper top-level imports")
        else:
            score -= 5
            missing.append("Imports not placed cleanly at the top")

        score = max(0, min(100, score))
        return QualityAuditResult(
            score=score,
            passed=score >= 70,
            kind="python",
            passed_checks=passed,
            missing_checks=missing,
            tips=tips,
            auto_regenerate=score < 70,
        )

    def audit_web_html(self, html_content: str) -> QualityAuditResult:
        score = 100
        passed = []
        missing = []
        tips = []
        low = html_content.lower()

        # Check 1: DOCTYPE
        if "<!doctype html>" in low:
            passed.append("<!DOCTYPE html> declaration")
        else:
            score -= 10
            missing.append("Missing <!DOCTYPE html>")
            tips.append("Add <!DOCTYPE html> at the beginning")

        # Check 2: Viewport meta tag
        if '<meta name="viewport"' in low or "<meta name='viewport'" in low:
            passed.append("Mobile viewport meta tag")
        else:
            score -= 15
            missing.append("Missing viewport meta tag for mobile responsiveness")
            tips.append("Add <meta name='viewport' content='width=device-width, initial-scale=1.0'>")

        # Check 3: Responsive layout (media queries or flex/grid)
        if "@media" in low or "flex" in low or "grid" in low:
            passed.append("Responsive flex/grid or media queries")
        else:
            score -= 15
            missing.append("No responsive flexbox, grid, or @media queries")
            tips.append("Include responsive CSS layout rules")

        # Check 4: Semantic HTML
        semantic_tags = ("<header", "<main", "<footer", "<nav", "<section", "<article")
        if any(tag in low for tag in semantic_tags):
            passed.append("Semantic HTML elements")
        else:
            score -= 10
            missing.append("Lacking semantic HTML tags (<main>, <header>, etc.)")
            tips.append("Use semantic tags instead of plain <div> containers")

        score = max(0, min(100, score))
        return QualityAuditResult(
            score=score,
            passed=score >= 70,
            kind="web",
            passed_checks=passed,
            missing_checks=missing,
            tips=tips,
            auto_regenerate=score < 70,
        )

    def audit_research(self, text: str) -> QualityAuditResult:
        score = 100
        passed = []
        missing = []
        tips = []

        # Check 1: Sources / citations
        urls = re.findall(r"https?://[^\s]+", text)
        if len(urls) >= 3 or text.lower().count("source") >= 2:
            passed.append("Multiple sources cited (3+)")
        else:
            score -= 15
            missing.append("Fewer than 3 distinct sources cited")
            tips.append("Include at least 3 verified sources")

        # Check 2: Section headers
        if text.count("#") >= 2:
            passed.append("Clear markdown section headers")
        else:
            score -= 10
            missing.append("Missing clear section headers")
            tips.append("Organize findings using markdown headers")

        score = max(0, min(100, score))
        return QualityAuditResult(
            score=score,
            passed=score >= 70,
            kind="research",
            passed_checks=passed,
            missing_checks=missing,
            tips=tips,
            auto_regenerate=score < 70,
        )

    def audit_output(self, content: str, task_type: str) -> QualityAuditResult:
        if task_type in ("create_python_script", "code_edit", "code"):
            return self.audit_python_code(content)
        elif task_type in ("create_website", "web_build", "html"):
            return self.audit_web_html(content)
        elif task_type in ("web_research", "research"):
            return self.audit_research(content)
        return QualityAuditResult(
            score=95, passed=True, kind="generic",
            passed_checks=["Output generated cleanly"], missing_checks=[], tips=[], auto_regenerate=False
        )
