# src/assistant_22b/security/gate2_masker.py
from __future__ import annotations

from dataclasses import dataclass

from gongmun_doctor.llm.pii_masker import PIIMasker


@dataclass
class MaskResult:
    masked_text: str
    was_masked: bool


class Gate2Masker:
    """Wraps P1's PIIMasker. In BMVP: runs masking but does not block.
    External LLM calls are not yet wired, so masked_text is computed
    but not transmitted anywhere — recorded for audit purposes only.
    """

    def __init__(self) -> None:
        self._masker = PIIMasker()

    def process(self, text: str) -> MaskResult:
        masked = self._masker.mask(text)
        return MaskResult(masked_text=masked, was_masked=(masked != text))
