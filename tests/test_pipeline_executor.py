# tests/test_pipeline_executor.py
from pathlib import Path
from assistant_22b.pipeline.executor import PipelineExecutor
from assistant_22b.security.auditor import SecurityAuditor
from assistant_22b.agents.registry import AgentRegistry


AGENTS_DIR = (
    Path(__file__).parent.parent / "src" / "assistant_22b" / "agents"
)


def make_executor(tmp_path: Path) -> PipelineExecutor:
    auditor = SecurityAuditor(
        db_path=tmp_path / "audit.db",
        key_path=tmp_path / ".audit_key",
    )
    registry = AgentRegistry(AGENTS_DIR)
    return PipelineExecutor(auditor=auditor, registry=registry)


def test_pipeline_returns_context(tmp_path):
    executor = make_executor(tmp_path)
    ctx = executor.run("이 공문을 교정해줘")
    assert ctx.request_id is not None
    assert ctx.completed_at is not None


def test_pipeline_has_all_four_gate_records(tmp_path):
    executor = make_executor(tmp_path)
    ctx = executor.run("공문서 교정 요청")
    gates = [g.gate for g in ctx.gate_log]
    assert 1 in gates
    assert 2 in gates
    assert 3 in gates
    assert 4 in gates


def test_pipeline_assigns_sensitivity(tmp_path):
    executor = make_executor(tmp_path)
    ctx = executor.run("보조금 지급 현황 보고서를 교정해줘")
    assert ctx.sensitivity in ("public", "internal", "confidential", "secret")


def test_pipeline_with_pii_text_sets_internal_or_higher(tmp_path, pii_text):
    executor = make_executor(tmp_path)
    ctx = executor.run(pii_text)
    assert ctx.sensitivity in ("internal", "confidential", "secret")


def test_pipeline_produces_agent_result(tmp_path):
    executor = make_executor(tmp_path)
    ctx = executor.run("공문 교정해줘")
    assert len(ctx.agent_results) >= 1
    result = ctx.agent_results[0]
    assert result.agent_id == "administrative"
    assert isinstance(result.output, str)


def test_pipeline_agent_exception_does_not_crash(tmp_path, monkeypatch):
    """If an agent raises, pipeline still completes and records the error."""
    from assistant_22b.agents.administrative.agent import AdministrativeAgent

    def boom(self, ctx):
        raise RuntimeError("simulated agent crash")

    monkeypatch.setattr(AdministrativeAgent, "process", boom)
    executor = make_executor(tmp_path)
    ctx = executor.run("공문 교정")
    assert ctx.completed_at is not None
    error_results = [r for r in ctx.agent_results if r.error is not None]
    assert len(error_results) == 1
