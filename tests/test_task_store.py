"""Tests for TaskStore."""
from __future__ import annotations
from datetime import datetime, timedelta
import pytest
from assistant_22b.storage.tasks import TaskStore


@pytest.fixture
def store(tmp_path):
    return TaskStore(
        db_path=tmp_path / "tasks.db",
        key_path=tmp_path / ".tasks_key",
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_add_and_list_open(store):
    task_id = store.add("보고서 작성")
    tasks = store.list_open()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "보고서 작성"
    assert tasks[0]["status"] == "open"
    assert tasks[0]["task_id"] == task_id


def test_add_with_due_date_and_priority(store):
    store.add("회의 준비", due_date="2026-03-25", priority=1)
    tasks = store.list_open()
    assert tasks[0]["due_date"] == "2026-03-25"
    assert tasks[0]["priority"] == 1


def test_mark_done_removes_from_list_open(store):
    task_id = store.add("완료할 일")
    result = store.mark_done(task_id)
    assert result is True
    assert store.list_open() == []


def test_delete_removes_task(store):
    task_id = store.add("삭제할 일")
    result = store.delete(task_id)
    assert result is True
    assert store.list_open() == []


def test_update_due_date(store):
    task_id = store.add("수정할 일")
    result = store.update(task_id, due_date="2026-04-01")
    assert result is True
    tasks = store.list_open()
    assert tasks[0]["due_date"] == "2026-04-01"


def test_update_returns_false_for_unknown_task(store):
    assert store.update("nonexistent-id", due_date="2026-04-01") is False


def test_delete_returns_false_for_unknown_task(store):
    assert store.delete("nonexistent-id") is False


def test_mark_done_returns_false_for_unknown_task(store):
    assert store.mark_done("nonexistent-id") is False


# ── Encryption ────────────────────────────────────────────────────────────────

def test_blob_is_not_plaintext(tmp_path):
    """Raw SQLite bytes must not contain the plaintext title."""
    import sqlite3
    store = TaskStore(db_path=tmp_path / "t.db", key_path=tmp_path / ".k")
    store.add("비밀 할일")
    raw_bytes = (tmp_path / "t.db").read_bytes()
    assert b"\xeb\xb9\x84\xeb\xb0\x80" not in raw_bytes  # UTF-8 for "비밀"


def test_key_auto_created_in_nested_dir(tmp_path):
    key_path = tmp_path / "nested" / ".tasks_key"
    store = TaskStore(db_path=tmp_path / "t.db", key_path=key_path)
    store.add("테스트")
    assert key_path.exists()


def test_corrupt_blob_skipped_gracefully(tmp_path):
    """A row with garbage blob is silently skipped; other rows unaffected."""
    import sqlite3
    store = TaskStore(db_path=tmp_path / "t.db", key_path=tmp_path / ".k")
    task_id = store.add("정상 할일")

    # Inject a corrupt blob row directly
    with sqlite3.connect(tmp_path / "t.db") as conn:
        conn.execute(
            "INSERT INTO tasks (task_id, created_at, blob) VALUES (?, ?, ?)",
            ("bad-id", "2026-01-01", b"not-encrypted"),
        )

    tasks = store.list_open()
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == task_id


def test_persists_across_instances(tmp_path):
    db = tmp_path / "t.db"
    key = tmp_path / ".k"
    s1 = TaskStore(db_path=db, key_path=key)
    task_id = s1.add("지속성 테스트")

    s2 = TaskStore(db_path=db, key_path=key)
    tasks = s2.list_open()
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == task_id


# ── Filtering ─────────────────────────────────────────────────────────────────

def test_list_open_excludes_done_tasks(store):
    t1 = store.add("열린 할일")
    t2 = store.add("완료된 할일")
    store.mark_done(t2)
    tasks = store.list_open()
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == t1


def test_list_open_filter_today(store):
    today = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    store.add("오늘 할일", due_date=today)
    store.add("어제 할일", due_date=yesterday)
    store.add("날짜 없음")
    tasks = store.list_open(filter="today")
    assert len(tasks) == 1
    assert tasks[0]["due_date"] == today


def test_list_open_filter_week(store):
    today = datetime.now().date().isoformat()
    far_future = "2099-12-31"
    store.add("이번 주 할일", due_date=today)
    store.add("먼 미래 할일", due_date=far_future)
    tasks = store.list_open(filter="week")
    assert len(tasks) == 1
    assert tasks[0]["due_date"] == today


def test_query_due_soon_returns_within_window(store):
    now = datetime.now()
    soon = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    far = (now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M")
    store.add("곧 마감", due_date=soon)
    store.add("나중에", due_date=far)
    store.add("날짜 없음")
    due = store.query_due_soon(hours=24)
    assert len(due) == 1
    assert due[0]["title"] == "곧 마감"


def test_query_due_soon_excludes_past_tasks(store):
    """Tasks with due_date in the past must NOT appear in query_due_soon."""
    past = (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M")
    store.add("이미 지난 일", due_date=past)
    due = store.query_due_soon(hours=24)
    assert due == []
