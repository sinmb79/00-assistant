# tests/test_gate4_logger.py
import hashlib
import json
import sqlite3
from pathlib import Path
from assistant_22b.security.gate4_logger import Gate4Logger
from assistant_22b.pipeline.context import AgentResult, GateRecord, PipelineContext
from datetime import datetime


def make_context(tmp_path: Path) -> PipelineContext:
    ctx = PipelineContext(request_id="test-req-audit", input_text="테스트 공문")
    ctx.sensitivity = "internal"
    ctx.gate_log.append(GateRecord(gate=1, passed=True, timestamp=datetime.now()))
    ctx.agent_results.append(
        AgentResult(agent_id="administrative", output="교정 완료", citations=[], raw=[])
    )
    return ctx


def test_gate4_creates_db_file(tmp_path):
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)
    logger.log(ctx)
    assert db.exists()


def test_gate4_creates_key_file(tmp_path):
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)
    logger.log(ctx)
    assert key.exists()


def test_gate4_log_is_readable(tmp_path):
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)
    logger.log(ctx)
    records = logger.read_all()
    assert len(records) == 1
    assert records[0]["request_id"] == "test-req-audit"


def test_gate4_input_is_hashed_not_stored_raw(tmp_path):
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)
    logger.log(ctx)
    records = logger.read_all()
    expected_hash = hashlib.sha256("테스트 공문".encode()).hexdigest()
    assert records[0]["input_hash"] == expected_hash
    assert "테스트 공문" not in json.dumps(records[0])


def test_gate4_failure_does_not_raise(tmp_path, monkeypatch):
    """Gate 4 must not crash the pipeline even if sqlite3.connect fails."""
    import sqlite3 as _sqlite3
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)

    # Force every sqlite3.connect call to raise OperationalError
    def broken_connect(*args, **kwargs):
        raise _sqlite3.OperationalError("simulated disk failure")

    monkeypatch.setattr("assistant_22b.security.gate4_logger.sqlite3.connect", broken_connect)
    # Must not raise despite the forced failure
    logger.log(ctx)  # should silently swallow and print to stderr
