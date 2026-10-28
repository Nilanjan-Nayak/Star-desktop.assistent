from __future__ import annotations
import logging
from .protocol import HiveResult

log = logging.getLogger("star.hive.critic")


class CriticAgent:
    """Critic Agent that reviews all outputs, rejecting any score < 70."""

    def review(self, result: HiveResult) -> HiveResult:
        log.info("Critic reviewing result from %s (Score: %d)", result.agent, result.quality_score)
        if result.quality_score < 70:
            result.status = "retry"
            result.error = f"Quality score {result.quality_score} below mandatory threshold of 70."
        return result
