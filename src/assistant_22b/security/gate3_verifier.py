# src/assistant_22b/security/gate3_verifier.py
from __future__ import annotations

from assistant_22b.pipeline.context import AgentResult
from assistant_22b.security.gate1_classifier import Gate1Classifier


class Gate3Verifier:
    """Verifies agent results:
    (a) output does not leak PII
    (b) every cited rule_id exists in the raw CorrectionItems
    """

    def __init__(self) -> None:
        self._classifier = Gate1Classifier()

    def verify(self, result: AgentResult) -> list[str]:
        """Returns list of issue strings. Empty list = passed."""
        issues: list[str] = []

        # (a) PII leak check
        pii_check = self._classifier.classify(result.output)
        if pii_check.detected_pii:
            issues.append(f"PII in output: {pii_check.detected_pii}")

        # (b) Citation integrity
        raw_rule_ids = {
            getattr(item, "rule_id", None) for item in result.raw
        } - {None}
        for citation in result.citations:
            if citation not in raw_rule_ids:
                issues.append(f"Citation '{citation}' not found in raw results")

        return issues
