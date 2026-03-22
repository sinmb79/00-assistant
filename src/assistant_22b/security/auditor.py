# src/assistant_22b/security/auditor.py
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from assistant_22b.pipeline.context import GateRecord, PipelineContext
from assistant_22b.security.gate1_classifier import Gate1Classifier
from assistant_22b.security.gate2_masker import Gate2Masker
from assistant_22b.security.gate3_verifier import Gate3Verifier
from assistant_22b.security.gate4_logger import Gate4Logger


class SecurityAuditor:
    def __init__(self, db_path: Path, key_path: Path) -> None:
        self._classifier = Gate1Classifier()
        self._masker = Gate2Masker()
        self._verifier = Gate3Verifier()
        self._logger = Gate4Logger(db_path=db_path, key_path=key_path)

    def gate1(self, context: PipelineContext) -> GateRecord:
        result = self._classifier.classify(context.input_text)
        context.sensitivity = result.sensitivity
        record = GateRecord(
            gate=1,
            passed=True,
            timestamp=datetime.now(),
            notes=f"sensitivity={result.sensitivity}; pii={result.detected_pii}",
        )
        context.gate_log.append(record)
        return record

    def gate2(self, context: PipelineContext) -> GateRecord:
        result = self._masker.process(context.input_text)
        record = GateRecord(
            gate=2,
            passed=True,
            timestamp=datetime.now(),
            notes=f"was_masked={result.was_masked}; external_sent=False",
        )
        context.gate_log.append(record)
        return record

    def gate3(self, context: PipelineContext) -> GateRecord:
        all_issues: list[str] = []
        for agent_result in context.agent_results:
            issues = self._verifier.verify(agent_result)
            if issues:
                agent_result.verified = False
                all_issues.extend(issues)
        passed = len(all_issues) == 0
        record = GateRecord(
            gate=3,
            passed=passed,
            timestamp=datetime.now(),
            notes="; ".join(all_issues) if all_issues else "ok",
        )
        context.gate_log.append(record)
        return record

    def gate4(self, context: PipelineContext) -> GateRecord:
        """Logs audit record. Never raises — pipeline safety gate."""
        try:
            self._logger.log(context)
            record = GateRecord(
                gate=4,
                passed=True,
                timestamp=datetime.now(),
                notes="logged",
            )
        except Exception as exc:  # pragma: no cover
            print(f"[SecurityAuditor] Gate 4 failed: {exc}", file=sys.stderr)
            record = GateRecord(
                gate=4,
                passed=False,
                timestamp=datetime.now(),
                notes=str(exc),
            )
        context.gate_log.append(record)
        return record
