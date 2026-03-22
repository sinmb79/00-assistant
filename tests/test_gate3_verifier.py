# tests/test_gate3_verifier.py
import pytest
from dataclasses import dataclass
from assistant_22b.security.gate3_verifier import Gate3Verifier
from assistant_22b.pipeline.context import AgentResult


@dataclass
class FakeCorrectionItem:
    """Mimics gongmun_doctor.report.markdown.CorrectionItem for testing."""
    rule_id: str
    rule_desc: str = "테스트 규칙 설명"
    rule_source: str = "테스트 출처"
    layer: str = "L1_test"
    original_text: str = "오류"
    corrected_text: str = "정상"
    paragraph_index: int = 0


def test_clean_result_passes_verification():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="이 문서는 교정이 완료되었습니다.",
        citations=["L1-001"],
        raw=[FakeCorrectionItem(rule_id="L1-001")],
    )
    issues = verifier.verify(result)
    assert issues == []


def test_pii_in_output_is_flagged():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="담당자 전화: 010-9999-0000",
        citations=[],
        raw=[],
    )
    issues = verifier.verify(result)
    assert any("PII" in issue for issue in issues)


def test_missing_citation_is_flagged():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="교정 완료",
        citations=["L1-GHOST"],  # not in raw
        raw=[FakeCorrectionItem(rule_id="L1-001")],
    )
    issues = verifier.verify(result)
    assert any("L1-GHOST" in issue for issue in issues)


def test_all_citations_matched_passes():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="교정 완료",
        citations=["L1-001", "L2-003"],
        raw=[
            FakeCorrectionItem(rule_id="L1-001"),
            FakeCorrectionItem(rule_id="L2-003"),
        ],
    )
    issues = verifier.verify(result)
    assert issues == []


def test_empty_citations_and_raw_passes():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="교정 사항 없음",
        citations=[],
        raw=[],
    )
    issues = verifier.verify(result)
    assert issues == []
