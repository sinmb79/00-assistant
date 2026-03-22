# tests/test_security_auditor.py
from pathlib import Path
from assistant_22b.security.auditor import SecurityAuditor
from assistant_22b.pipeline.context import AgentResult, PipelineContext


def make_auditor(tmp_path: Path) -> SecurityAuditor:
    return SecurityAuditor(
        db_path=tmp_path / "audit.db",
        key_path=tmp_path / ".audit_key",
    )


def test_gate1_sets_sensitivity_on_context(pii_context, tmp_path):
    auditor = make_auditor(tmp_path)
    auditor.gate1(pii_context)
    assert pii_context.sensitivity == "internal"


def test_gate1_appends_to_gate_log(sample_context, tmp_path):
    auditor = make_auditor(tmp_path)
    auditor.gate1(sample_context)
    assert len(sample_context.gate_log) == 1
    assert sample_context.gate_log[0].gate == 1


def test_gate2_appends_gate_record(sample_context, tmp_path):
    auditor = make_auditor(tmp_path)
    auditor.gate2(sample_context)
    assert any(g.gate == 2 for g in sample_context.gate_log)


def test_gate3_marks_result_unverified_on_pii(tmp_path):
    auditor = make_auditor(tmp_path)
    ctx = PipelineContext(request_id="x", input_text="ok")
    ctx.agent_results.append(
        AgentResult(
            agent_id="a",
            output="전화: 010-9999-0000",  # PII in output
            citations=[],
            raw=[],
        )
    )
    auditor.gate3(ctx)
    assert ctx.agent_results[0].verified is False


def test_gate3_passes_clean_result(tmp_path):
    """Agent result with no PII in output and no citations passes Gate 3."""
    auditor = make_auditor(tmp_path)
    ctx = PipelineContext(request_id="y", input_text="clean")
    clean_result = AgentResult(
        agent_id="b", output="교정 사항이 없습니다.", citations=[], raw=[]
    )
    ctx.agent_results.append(clean_result)
    auditor.gate3(ctx)
    assert ctx.agent_results[0].verified is True


def test_gate4_writes_audit_log(sample_context, tmp_path):
    auditor = make_auditor(tmp_path)
    auditor.gate4(sample_context)
    db_path = tmp_path / "audit.db"
    assert db_path.exists()
