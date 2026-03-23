"""Tests for TaskAgent."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from assistant_22b.agents.task.agent import TaskAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext
from assistant_22b.storage.tasks import TaskStore

TASK_MANIFEST_DIR = (
    Path(__file__).parent.parent
    / "src" / "assistant_22b" / "agents" / "task"
)


@pytest.fixture
def store(tmp_path):
    return TaskStore(
        db_path=tmp_path / "tasks.db",
        key_path=tmp_path / ".tasks_key",
    )


@pytest.fixture
def agent(store):
    return TaskAgent(TASK_MANIFEST_DIR, store=store)


def ctx(text: str) -> PipelineContext:
    return PipelineContext(request_id="r", input_text=text)


# ── Agent metadata ─────────────────────────────────────────────────────────

def test_agent_id_is_task(agent):
    assert agent.agent_id == "task"


def test_agent_returns_agent_result(agent):
    result = agent.process(ctx("할일 목록 알려줘"))
    assert isinstance(result, AgentResult)


# ── ADD intent ────────────────────────────────────────────────────────────

def test_add_creates_task(agent, store):
    result = agent.process(ctx("보고서 작성 추가"))
    assert result.error is None
    tasks = store.list_open()
    assert len(tasks) == 1
    assert "보고서" in tasks[0]["title"]


def test_add_output_confirms_title(agent):
    result = agent.process(ctx("회의록 등록"))
    assert "회의록" in result.output


def test_add_with_date_extracts_due_date(agent, store):
    result = agent.process(ctx("보고서 추가 마감 2026-04-01"))
    tasks = store.list_open()
    assert tasks[0]["due_date"] == "2026-04-01"


# ── LIST intent ───────────────────────────────────────────────────────────

def test_list_returns_open_tasks(agent, store):
    store.add("할일 A")
    store.add("할일 B")
    result = agent.process(ctx("할일 목록 알려줘"))
    assert "할일 A" in result.output
    assert "할일 B" in result.output


def test_list_empty_returns_message(agent):
    result = agent.process(ctx("목록 알려줘"))
    assert result.error is None
    assert "할일이 없습니다" in result.output


def test_list_today_filter(agent, store):
    from datetime import datetime
    today = datetime.now().date().isoformat()
    store.add("오늘 할일", due_date=today)
    store.add("언제든지 할일")
    result = agent.process(ctx("오늘 뭐 해야 해?"))
    assert "오늘 할일" in result.output
    assert "언제든지 할일" not in result.output


def test_list_week_filter(agent, store):
    from datetime import datetime
    today = datetime.now().date().isoformat()
    store.add("이번 주 할일", due_date=today)
    result = agent.process(ctx("이번 주 목록"))
    assert "이번 주 할일" in result.output


# ── DONE intent ───────────────────────────────────────────────────────────

def test_done_marks_task(agent, store):
    store.add("완료할 보고서")
    result = agent.process(ctx("완료 보고서"))
    assert result.error is None
    assert store.list_open() == []


def test_done_not_found_returns_message(agent):
    result = agent.process(ctx("없는 할일 완료"))
    assert result.error is None
    assert "찾지 못했습니다" in result.output


# ── DELETE intent ─────────────────────────────────────────────────────────

def test_delete_removes_task(agent, store):
    store.add("삭제할 회의록")
    result = agent.process(ctx("회의록 삭제"))
    assert result.error is None
    assert store.list_open() == []


def test_delete_not_found_returns_message(agent):
    result = agent.process(ctx("없는 할일 삭제"))
    assert result.error is None
    assert "찾지 못했습니다" in result.output


# ── UPDATE intent ─────────────────────────────────────────────────────────

def test_update_changes_due_date(agent, store):
    store.add("수정할 보고서")
    result = agent.process(ctx("보고서 수정 2026-05-01"))
    assert result.error is None
    tasks = store.list_open()
    assert tasks[0]["due_date"] == "2026-05-01"


def test_update_not_found_returns_message(agent):
    result = agent.process(ctx("없는 할일 수정 2026-05-01"))
    assert result.error is None
    assert "찾지 못했습니다" in result.output


# ── UNKNOWN intent ────────────────────────────────────────────────────────

def test_unknown_returns_clarification(agent):
    result = agent.process(ctx("무슨 말인지 모르겠어"))
    assert result.error is None
    assert "추가" in result.output or "조회" in result.output or "완료" in result.output


# ── Classify priority ─────────────────────────────────────────────────────

def test_done_keyword_beats_list_keyword(agent, store):
    """DONE is checked before LIST — '목록 완료' classifies as DONE (no open tasks → not-found msg)."""
    result = agent.process(ctx("목록 완료"))
    assert "찾지 못했습니다" in result.output


# ── Error handling ────────────────────────────────────────────────────────

def test_store_failure_returns_error_result(agent):
    """TaskStore access failure → AgentResult.error is non-empty string."""
    agent._store = MagicMock()
    agent._store.list_open.side_effect = RuntimeError("DB crash")
    result = agent.process(ctx("목록 알려줘"))
    assert isinstance(result.error, str)
    assert len(result.error) > 0
