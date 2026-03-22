# tests/conftest.py
import json
import pytest
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from assistant_22b.pipeline.context import AgentResult, GateRecord, PipelineContext


@pytest.fixture
def clean_text():
    return "이 문서는 교정이 필요한 내용을 담고 있습니다."


@pytest.fixture
def pii_text():
    return "담당자 김철수(010-1234-5678)에게 연락 바랍니다."


@pytest.fixture
def rrn_text():
    return "주민등록번호: 850101-1234567"


@pytest.fixture
def sample_context(clean_text):
    return PipelineContext(
        request_id="test-req-001",
        input_text=clean_text,
    )


@pytest.fixture
def pii_context(pii_text):
    return PipelineContext(
        request_id="test-req-002",
        input_text=pii_text,
    )


@pytest.fixture
def sample_agent_result():
    return AgentResult(
        agent_id="test-agent",
        output="교정된 텍스트입니다.",
        citations=["L1-TEST-001"],
        raw=[],
    )


@pytest.fixture
def tmp_rules_dir(tmp_path):
    """Temp directory with a single known correction rule for deterministic tests."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rule_data = {
        "meta": {"layer": "L1_test"},
        "rules": [
            {
                "id": "L1-TEST-001",
                "type": "exact_replace",
                "search": "테스트오류",
                "replace": "테스트정상",
                "desc": "테스트 규칙",
                "source": "테스트 출처",
            }
        ],
    }
    (rules_dir / "L1_test.json").write_text(
        json.dumps(rule_data, ensure_ascii=False), encoding="utf-8"
    )
    return rules_dir


# P1 CorrectionItem has fields: rule_id, rule_desc, rule_source, layer,
# original_text, corrected_text, paragraph_index.
# FakeCorrectionItem mirrors this for Gate 3 tests that inspect _format_output.
@dataclass
class FakeCorrectionItem:
    """Stub matching gongmun_doctor.report.markdown.CorrectionItem interface."""
    rule_id: str
    rule_desc: str = "테스트 규칙 설명"
    rule_source: str = "테스트 출처"
    layer: str = "L1_test"
    original_text: str = "오류"
    corrected_text: str = "정상"
    paragraph_index: int = 0


@pytest.fixture
def tmp_manifest_dir(tmp_path):
    """Temp agent directory with manifest.json."""
    manifest = {
        "id": "test-agent",
        "name": "테스트 에이전트",
        "icon": "🧪",
        "version": "0.0.1",
        "triggers": ["테스트"],
        "llm_preference": "local",
        "sensitivity": "internal",
        "fallback": False,
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return tmp_path
