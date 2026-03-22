# tests/test_administrative_agent.py
from pathlib import Path
from assistant_22b.agents.administrative.agent import AdministrativeAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext


ADMIN_MANIFEST_DIR = (
    Path(__file__).parent.parent
    / "src" / "assistant_22b" / "agents" / "administrative"
)


def test_administrative_agent_returns_agent_result(sample_context):
    agent = AdministrativeAgent(ADMIN_MANIFEST_DIR)
    result = agent.process(sample_context)
    assert isinstance(result, AgentResult)
    assert result.agent_id == "administrative"


def test_administrative_agent_citations_match_raw(sample_context):
    agent = AdministrativeAgent(ADMIN_MANIFEST_DIR)
    result = agent.process(sample_context)
    raw_rule_ids = [getattr(item, "rule_id", None) for item in result.raw]
    assert result.citations == raw_rule_ids


def test_administrative_agent_with_known_rule(tmp_rules_dir):
    """Uses a controlled tmp rule: 테스트오류 → 테스트정상."""
    agent = AdministrativeAgent(ADMIN_MANIFEST_DIR, rules_dir=tmp_rules_dir)
    ctx = PipelineContext(request_id="r-rule", input_text="이 문서에 테스트오류가 있습니다.")
    result = agent.process(ctx)
    assert "L1-TEST-001" in result.citations
    assert "테스트정상" in result.output


def test_administrative_agent_clean_text_has_empty_citations(tmp_rules_dir):
    agent = AdministrativeAgent(ADMIN_MANIFEST_DIR, rules_dir=tmp_rules_dir)
    ctx = PipelineContext(request_id="r-clean", input_text="오류가 없는 문장입니다.")
    result = agent.process(ctx)
    assert result.citations == []
    assert result.raw == []
