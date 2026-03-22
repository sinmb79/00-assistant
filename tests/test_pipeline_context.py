# tests/test_pipeline_context.py
from datetime import datetime
from assistant_22b.pipeline.context import AgentResult, GateRecord, PipelineContext


def test_pipeline_context_default_sensitivity():
    ctx = PipelineContext(request_id="r1", input_text="hello")
    assert ctx.sensitivity == "public"


def test_pipeline_context_empty_gate_log_by_default():
    ctx = PipelineContext(request_id="r1", input_text="hello")
    assert ctx.gate_log == []


def test_pipeline_context_empty_agent_results_by_default():
    ctx = PipelineContext(request_id="r1", input_text="hello")
    assert ctx.agent_results == []


def test_pipeline_context_has_created_at():
    before = datetime.now()
    ctx = PipelineContext(request_id="r1", input_text="hello")
    after = datetime.now()
    assert before <= ctx.created_at <= after


def test_gate_record_stores_all_fields():
    ts = datetime.now()
    record = GateRecord(gate=1, passed=True, timestamp=ts, notes="test note")
    assert record.gate == 1
    assert record.passed is True
    assert record.timestamp == ts
    assert record.notes == "test note"


def test_gate_record_default_notes_empty():
    record = GateRecord(gate=2, passed=False, timestamp=datetime.now())
    assert record.notes == ""


def test_agent_result_default_verified_true():
    result = AgentResult(
        agent_id="a1", output="out", citations=[], raw=[]
    )
    assert result.verified is True


def test_agent_result_default_error_none():
    result = AgentResult(
        agent_id="a1", output="out", citations=[], raw=[]
    )
    assert result.error is None
