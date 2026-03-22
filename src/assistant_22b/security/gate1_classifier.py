# src/assistant_22b/security/gate1_classifier.py
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SEVERITY_ORDER = {"public": 0, "internal": 1, "confidential": 2, "secret": 3}

_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # (sensitivity, pii_type, compiled_pattern)
    # Confidential — highest priority
    ("confidential", "주민번호", re.compile(r"\d{6}-[1-4]\d{6}")),
    # Internal
    ("internal", "전화번호", re.compile(r"\b01[016789]-\d{3,4}-\d{4}\b")),
    ("internal", "전화번호", re.compile(r"\b02-\d{3,4}-\d{4}\b")),
    ("internal", "전화번호", re.compile(r"\b0[3-9]\d-\d{3,4}-\d{4}\b")),
    ("internal", "이메일", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    ("internal", "계좌번호", re.compile(r"(?<!\d)\d{3,6}-\d{2,6}-\d{4,8}(?!\d)")),
]


@dataclass
class ClassificationResult:
    sensitivity: str
    detected_pii: list[str] = field(default_factory=list)


class Gate1Classifier:
    def classify(self, text: str) -> ClassificationResult:
        detected: list[str] = []
        max_sensitivity = "public"

        for sensitivity, pii_type, pattern in _PATTERNS:
            if pattern.search(text) and pii_type not in detected:
                detected.append(pii_type)
                if _SEVERITY_ORDER[sensitivity] > _SEVERITY_ORDER[max_sensitivity]:
                    max_sensitivity = sensitivity

        return ClassificationResult(sensitivity=max_sensitivity, detected_pii=detected)
