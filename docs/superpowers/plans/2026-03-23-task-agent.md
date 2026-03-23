# Task Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a rule-based `TaskAgent` (Phase B item 7) with Fernet-encrypted SQLite task storage, keyword-based intent classification, and tray notification polling.

**Architecture:** `TaskStore` (Fernet+SQLite, mirrors `ConversationStore`) stores tasks. `TaskAgent(BaseAgent)` classifies intent by keyword matching, delegates to `TaskStore`, returns `AgentResult`. `AssistantApp` polls `TaskStore.query_due_soon()` via `root.after()`. `AssistantConfig` gains `task_check_interval_minutes`.

**Tech Stack:** Python 3.12, pytest 8+, cryptography (Fernet), sqlite3, uuid, re, tkinter root.after()

**Spec:** `docs/superpowers/specs/2026-03-23-task-agent-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/assistant_22b/config.py` | Modify | Add `task_check_interval_minutes: int = 60` to `AssistantConfig` |
| `src/assistant_22b/storage/tasks.py` | Create | `TaskStore` — Fernet-encrypted SQLite CRUD + queries |
| `src/assistant_22b/agents/task/__init__.py` | Create | Empty package marker |
| `src/assistant_22b/agents/task/manifest.json` | Create | Agent metadata + trigger keywords |
| `src/assistant_22b/agents/task/agent.py` | Create | `TaskAgent(BaseAgent)` — intent classification + dispatch |
| `src/assistant_22b/ui/app.py` | Modify | Wire `TaskStore` + `root.after()` deadline polling |
| `tests/test_config.py` | Modify | Add test for `task_check_interval_minutes` default |
| `tests/test_task_store.py` | Create | Full `TaskStore` unit tests |
| `tests/test_task_agent.py` | Create | Full `TaskAgent` unit tests |

---

## Task 1: Add `task_check_interval_minutes` to `AssistantConfig`

**Files:**
- Modify: `src/assistant_22b/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_task_check_interval_minutes_default(tmp_path):
    cfg = ConfigManager(config_path=tmp_path / "config.json")
    assert cfg.config.task_check_interval_minutes == 60


def test_task_check_interval_minutes_loads_from_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"task_check_interval_minutes": 30}', encoding="utf-8")
    cfg = ConfigManager(config_path=path)
    assert cfg.config.task_check_interval_minutes == 30
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_config.py::test_task_check_interval_minutes_default -v
```
Expected: `FAILED` — `AssistantConfig has no field 'task_check_interval_minutes'`

- [ ] **Step 3: Add the field to `AssistantConfig`**

In `src/assistant_22b/config.py`, add one line to the dataclass:

```python
@dataclass
class AssistantConfig:
    llm_mode: str = "none"
    llm_model_path: str = ""
    llm_provider: str = "claude"
    hotkey: str = "ctrl+shift+g"
    theme: str = "light"
    task_check_interval_minutes: int = 60   # ← add this line
```

- [ ] **Step 4: Run tests to confirm pass**

```
pytest tests/test_config.py -v
```
Expected: all pass (existing 6 + new 2 = 8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/assistant_22b/config.py tests/test_config.py
git commit -m "feat: add task_check_interval_minutes to AssistantConfig"
```

---

## Task 2: TaskStore — Fernet-encrypted SQLite

**Files:**
- Create: `src/assistant_22b/storage/tasks.py`
- Create: `tests/test_task_store.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_task_store.py`:

```python
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
```

- [ ] **Step 2: Run to confirm all fail**

```
pytest tests/test_task_store.py -v
```
Expected: `ERROR` — `ModuleNotFoundError: No module named 'assistant_22b.storage.tasks'`

- [ ] **Step 3: Create `TaskStore`**

Create `src/assistant_22b/storage/tasks.py`:

```python
"""Fernet-encrypted SQLite task store."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet


class TaskStore:
    """Stores and retrieves tasks in a Fernet-encrypted SQLite database."""

    def __init__(self, db_path: Path, key_path: Path) -> None:
        self._db_path = db_path
        self._fernet = self._load_or_create_key(key_path)
        self._init_db()

    # ── Public API ────────────────────────────────────────────────────────

    def add(self, title: str, due_date: str | None = None, priority: int = 2) -> str:
        """Insert a new open task. Returns the new task_id (UUID4 string)."""
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        payload = {
            "task_id": task_id,
            "title": title,
            "due_date": due_date,
            "priority": priority,
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
        blob = self._fernet.encrypt(json.dumps(payload, ensure_ascii=False).encode())
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, created_at, blob) VALUES (?, ?, ?)",
                (task_id, now, blob),
            )
        return task_id

    def list_open(self, filter: str | None = None) -> list[dict]:
        """Return open tasks, optionally filtered by 'today' or 'week'."""
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT blob FROM tasks ORDER BY id").fetchall()
        tasks = []
        for (blob,) in rows:
            try:
                data = json.loads(self._fernet.decrypt(blob).decode())
            except Exception:
                continue
            if data.get("status") != "open":
                continue
            if filter == "today" and not self._is_today(data.get("due_date")):
                continue
            if filter == "week" and not self._is_this_week(data.get("due_date")):
                continue
            tasks.append(data)
        return tasks

    def mark_done(self, task_id: str) -> bool:
        """Set task status to 'done'. Returns False if task_id not found."""
        return self._update_blob(task_id, {"status": "done"})

    def delete(self, task_id: str) -> bool:
        """Remove task row. Returns False if task_id not found."""
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        return cur.rowcount > 0

    def update(self, task_id: str, **kwargs) -> bool:
        """Update allowed fields: title, due_date, priority. Returns False if not found."""
        allowed = {"title", "due_date", "priority"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        return self._update_blob(task_id, updates)

    def query_due_soon(self, hours: int = 24) -> list[dict]:
        """Return open tasks with due_date between now and now+hours."""
        now_str = datetime.now().isoformat()
        cutoff = (datetime.now() + timedelta(hours=hours)).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT blob FROM tasks ORDER BY id").fetchall()
        result = []
        for (blob,) in rows:
            try:
                data = json.loads(self._fernet.decrypt(blob).decode())
            except Exception:
                continue
            if data.get("status") != "open":
                continue
            due = data.get("due_date")
            if due and now_str <= due <= cutoff:
                result.append(data)
        return result

    # ── Private helpers ───────────────────────────────────────────────────

    def _update_blob(self, task_id: str, changes: dict) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT id, blob FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                return False
            row_id, blob = row
            try:
                data = json.loads(self._fernet.decrypt(blob).decode())
            except Exception:
                return False
            data.update(changes)
            data["updated_at"] = datetime.now().isoformat()
            new_blob = self._fernet.encrypt(
                json.dumps(data, ensure_ascii=False).encode()
            )
            conn.execute("UPDATE tasks SET blob = ? WHERE id = ?", (new_blob, row_id))
        return True

    def _load_or_create_key(self, key_path: Path) -> Fernet:
        if key_path.exists():
            return Fernet(key_path.read_bytes())
        key = Fernet.generate_key()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(key)
        return Fernet(key)

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id    TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    blob       BLOB NOT NULL
                )
            """)

    @staticmethod
    def _is_today(due_date: str | None) -> bool:
        if not due_date:
            return False
        return due_date.startswith(datetime.now().date().isoformat())

    @staticmethod
    def _is_this_week(due_date: str | None) -> bool:
        if not due_date:
            return False
        try:
            due = datetime.fromisoformat(due_date[:10]).date()
        except ValueError:
            return False
        today = datetime.now().date()
        end_of_week = today + timedelta(days=(6 - today.weekday()))
        return today <= due <= end_of_week
```

- [ ] **Step 4: Run tests to confirm pass**

```
pytest tests/test_task_store.py -v
```
Expected: all 19 tests pass

- [ ] **Step 5: Run full suite to confirm no regression**

```
pytest tests/ -q
```
Expected: 112 passed (93 after Task 1 + 19 new)

- [ ] **Step 6: Commit**

```bash
git add src/assistant_22b/storage/tasks.py tests/test_task_store.py
git commit -m "feat: TaskStore — Fernet-encrypted SQLite task storage"
```

---

## Task 3: TaskAgent — BaseAgent wrapper

**Files:**
- Create: `src/assistant_22b/agents/task/__init__.py`
- Create: `src/assistant_22b/agents/task/manifest.json`
- Create: `src/assistant_22b/agents/task/agent.py`
- Create: `tests/test_task_agent.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_task_agent.py`:

```python
"""Tests for TaskAgent."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch
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
    # No open tasks exist, so DONE handler returns "찾지 못했습니다"
    assert "찾지 못했습니다" in result.output


# ── Error handling ────────────────────────────────────────────────────────

def test_store_failure_returns_error_result(agent):
    """TaskStore access failure → AgentResult.error is non-empty string."""
    agent._store = MagicMock()
    agent._store.list_open.side_effect = RuntimeError("DB crash")
    result = agent.process(ctx("목록 알려줘"))
    assert isinstance(result.error, str)
    assert len(result.error) > 0
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_task_agent.py -v
```
Expected: `ERROR` — `ModuleNotFoundError: No module named 'assistant_22b.agents.task'`

- [ ] **Step 3: Create the agent package files**

Create `src/assistant_22b/agents/task/__init__.py` (empty):
```python
```

Create `src/assistant_22b/agents/task/manifest.json`:
```json
{
  "id": "task",
  "name": "일정 에이전트",
  "icon": "📅",
  "version": "1.0.0",
  "triggers": ["추가", "등록", "할일", "해야", "만들어", "완료", "삭제", "목록", "이번 주", "수정", "일정"],
  "llm_preference": "local",
  "sensitivity": "internal",
  "fallback": false
}
```

Create `src/assistant_22b/agents/task/agent.py`:

```python
"""Task Agent — rule-based todo/schedule management."""
from __future__ import annotations

import re
from pathlib import Path

from assistant_22b.agents.base import BaseAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext
from assistant_22b.storage.tasks import TaskStore

_DATA_DIR = Path.home() / ".22b-assistant"

_DONE_KW = ["완료", "다 했어", "끝났어", "했어"]
_DELETE_KW = ["삭제", "취소", "지워"]
_UPDATE_KW = ["수정", "바꿔", "변경"]
_ADD_KW = ["추가", "등록", "할일", "해야", "만들어"]
_LIST_KW = ["오늘", "이번 주", "목록", "뭐 해야", "알려줘"]

_PRIORITY = {1: "높음", 2: "보통", 3: "낮음"}


class TaskAgent(BaseAgent):
    """Rule-based task management agent."""

    def __init__(self, manifest_dir: Path, store: TaskStore | None = None) -> None:
        super().__init__(manifest_dir)
        if store is not None:
            self._store = store
        else:
            data = _DATA_DIR
            db_dir = data / "db"
            db_dir.mkdir(parents=True, exist_ok=True)
            self._store = TaskStore(
                db_path=db_dir / "tasks.db",
                key_path=data / ".tasks_key",
            )

    def process(self, context: PipelineContext) -> AgentResult:
        try:
            return self._dispatch(context.input_text)
        except Exception as exc:
            return AgentResult(
                agent_id=self.agent_id,
                output="",
                citations=[],
                raw=[],
                error=f"TaskStore 접근 오류: {exc}",
            )

    # ── Intent dispatch ───────────────────────────────────────────────────

    def _dispatch(self, text: str) -> AgentResult:
        t = text.lower()
        intent = self._classify(t)
        if intent == "ADD":
            return self._handle_add(text)
        if intent == "LIST":
            return self._handle_list(t)
        if intent == "DONE":
            return self._handle_done(text)
        if intent == "DELETE":
            return self._handle_delete(text)
        if intent == "UPDATE":
            return self._handle_update(text)
        return AgentResult(
            agent_id=self.agent_id,
            output="무슨 일정 작업을 원하시나요? (추가/조회/완료/삭제)",
            citations=[],
            raw=[],
        )

    def _classify(self, text_lower: str) -> str:
        # Check higher-priority intents first to avoid keyword collisions
        for kw in _DONE_KW:
            if kw in text_lower:
                return "DONE"
        for kw in _DELETE_KW:
            if kw in text_lower:
                return "DELETE"
        for kw in _UPDATE_KW:
            if kw in text_lower:
                return "UPDATE"
        for kw in _ADD_KW:
            if kw in text_lower:
                return "ADD"
        for kw in _LIST_KW:
            if kw in text_lower:
                return "LIST"
        return "UNKNOWN"

    # ── Handlers ──────────────────────────────────────────────────────────

    def _handle_add(self, text: str) -> AgentResult:
        # Remove intent keyword(s) to extract title
        title = re.sub(
            r"(추가|등록|할일|해야|만들어)(해줘|해|줘|요|하기)?[:\s]*",
            "", text, flags=re.IGNORECASE
        ).strip()
        if not title:
            title = text.strip()

        # Extract ISO date if present
        due_match = re.search(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?", text)
        due_date = due_match.group() if due_match else None
        # Remove the date from title if it was extracted
        if due_date:
            title = title.replace(due_date, "").strip()

        self._store.add(title=title, due_date=due_date)
        msg = f"✅ 할일 추가됨: {title}"
        if due_date:
            msg += f" (마감: {due_date})"
        return AgentResult(agent_id=self.agent_id, output=msg, citations=[], raw=[])

    def _handle_list(self, text_lower: str) -> AgentResult:
        filter_ = None
        if "오늘" in text_lower:
            filter_ = "today"
        elif "이번 주" in text_lower:
            filter_ = "week"
        tasks = self._store.list_open(filter=filter_)
        if not tasks:
            label = {"today": "오늘", "week": "이번 주"}.get(filter_ or "", "")
            return AgentResult(
                agent_id=self.agent_id,
                output=f"{label + ' ' if label else ''}할일이 없습니다.",
                citations=[],
                raw=[],
            )
        lines = ["## 할일 목록\n"]
        for t in tasks:
            due = f" (마감: {t['due_date']})" if t.get("due_date") else ""
            pri = _PRIORITY.get(t.get("priority", 2), "보통")
            lines.append(f"- [{pri}] {t['title']}{due}")
        return AgentResult(
            agent_id=self.agent_id,
            output="\n".join(lines),
            citations=[],
            raw=[],
        )

    def _handle_done(self, text: str) -> AgentResult:
        matched = self._find_task_in_text(text, self._store.list_open())
        if not matched:
            return AgentResult(
                agent_id=self.agent_id,
                output="완료할 할일을 찾지 못했습니다. 할일 이름을 포함해서 말씀해 주세요.",
                citations=[],
                raw=[],
            )
        self._store.mark_done(matched["task_id"])
        return AgentResult(
            agent_id=self.agent_id,
            output=f"✅ 완료: {matched['title']}",
            citations=[],
            raw=[],
        )

    def _handle_delete(self, text: str) -> AgentResult:
        matched = self._find_task_in_text(text, self._store.list_open())
        if not matched:
            return AgentResult(
                agent_id=self.agent_id,
                output="삭제할 할일을 찾지 못했습니다. 할일 이름을 포함해서 말씀해 주세요.",
                citations=[],
                raw=[],
            )
        self._store.delete(matched["task_id"])
        return AgentResult(
            agent_id=self.agent_id,
            output=f"🗑️ 삭제됨: {matched['title']}",
            citations=[],
            raw=[],
        )

    def _handle_update(self, text: str) -> AgentResult:
        matched = self._find_task_in_text(text, self._store.list_open())
        if not matched:
            return AgentResult(
                agent_id=self.agent_id,
                output="수정할 할일을 찾지 못했습니다. 할일 이름을 포함해서 말씀해 주세요.",
                citations=[],
                raw=[],
            )
        due_match = re.search(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?", text)
        if due_match:
            self._store.update(matched["task_id"], due_date=due_match.group())
            return AgentResult(
                agent_id=self.agent_id,
                output=f"✏️ 수정됨: {matched['title']}",
                citations=[],
                raw=[],
            )
        return AgentResult(
            agent_id=self.agent_id,
            output="수정할 내용을 인식하지 못했습니다. 날짜 형식(YYYY-MM-DD)을 포함해서 말씀해 주세요.",
            citations=[],
            raw=[],
        )

    @staticmethod
    def _find_task_in_text(text: str, tasks: list[dict]) -> dict | None:
        text_lower = text.lower()
        for task in tasks:
            if task["title"].lower() in text_lower:
                return task
        return None
```

- [ ] **Step 4: Run tests to confirm pass**

```
pytest tests/test_task_agent.py -v
```
Expected: all 22 tests pass

- [ ] **Step 5: Run full suite to confirm no regression**

```
pytest tests/ -q
```
Expected: 135 passed (112 after Task 2 + 23 new)

- [ ] **Step 6: Commit**

```bash
git add src/assistant_22b/agents/task/ tests/test_task_agent.py
git commit -m "feat: TaskAgent — rule-based todo management with manifest routing"
```

---

## Task 4: Wire TaskStore + polling into AssistantApp

**Files:**
- Modify: `src/assistant_22b/ui/app.py`
- Modify: `tests/test_ui_app.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_app.py`:

```python
def test_app_has_task_store_attribute(tmp_path):
    """AssistantApp.__init__ wires a _task_store. Verified by constructing it directly."""
    from assistant_22b.ui.app import AssistantApp
    from assistant_22b.storage.tasks import TaskStore

    # Use __new__ to bypass full __init__ (AgentRegistry/HwpAdapter side-effects)
    app = AssistantApp.__new__(AssistantApp)
    (tmp_path / "db").mkdir()
    app._task_store = TaskStore(
        db_path=tmp_path / "db" / "tasks.db",
        key_path=tmp_path / ".tasks_key",
    )
    assert hasattr(app, "_task_store")
    assert isinstance(app._task_store, TaskStore)


def test_poll_due_tasks_calls_query_due_soon():
    """_poll_due_tasks calls TaskStore.query_due_soon and notifies on results."""
    from assistant_22b.ui.app import AssistantApp

    mock_store = MagicMock()
    mock_store.query_due_soon.return_value = [{"title": "마감 임박 보고서"}]

    app = AssistantApp.__new__(AssistantApp)
    app._task_store = mock_store
    app._window = None

    app._poll_due_tasks()
    mock_store.query_due_soon.assert_called_once()


def test_poll_due_tasks_no_crash_when_empty():
    """_poll_due_tasks does not crash when no tasks are due."""
    from assistant_22b.ui.app import AssistantApp

    mock_store = MagicMock()
    mock_store.query_due_soon.return_value = []

    app = AssistantApp.__new__(AssistantApp)
    app._task_store = mock_store
    app._window = None

    app._poll_due_tasks()  # must not raise
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_ui_app.py::test_app_has_task_store_attribute -v
```
Expected: `FAILED` — `AssistantApp.__init__` has no `_task_store`

- [ ] **Step 3: Wire TaskStore into AssistantApp**

In `src/assistant_22b/ui/app.py`:

Add import at the top:
```python
from assistant_22b.storage.tasks import TaskStore
```

In `__init__`, after `self._store = ConversationStore(...)`, add:
```python
        self._task_store = TaskStore(
            db_path=data / "db" / "tasks.db",
            key_path=data / ".tasks_key",
        )
```

Also create the `db/` subdirectory before `TaskStore` is constructed. Add after `data.mkdir(...)`:
```python
        (data / "db").mkdir(exist_ok=True)
```

Add the polling method to `AssistantApp`:
```python
    def _poll_due_tasks(self) -> None:
        """Check for tasks due within 24 h and post a notification if found."""
        try:
            due = self._task_store.query_due_soon(hours=24)
        except Exception:
            return
        if due and self._window and self._window._root:
            titles = ", ".join(t["title"] for t in due[:3])
            suffix = f" 외 {len(due) - 3}건" if len(due) > 3 else ""
            msg = f"⏰ 마감 임박: {titles}{suffix}"
            self._window._root.after(
                0, lambda: self._window._append_message("일정 알림", msg, "assistant")
            )
```

In the `run()` method, after `root = tk.Tk()`, add the polling schedule:
```python
        interval_ms = self._config_mgr.config.task_check_interval_minutes * 60 * 1000

        def _schedule_poll():
            self._poll_due_tasks()
            root.after(interval_ms, _schedule_poll)

        root.after(interval_ms, _schedule_poll)
```

- [ ] **Step 4: Run tests to confirm pass**

```
pytest tests/test_ui_app.py -v
```
Expected: all tests pass (existing + 3 new)

- [ ] **Step 5: Run full suite to confirm no regression**

```
pytest tests/ -q
```
Expected: 138 passed (135 after Task 3 + 3 new)

- [ ] **Step 6: Commit**

```bash
git add src/assistant_22b/ui/app.py tests/test_ui_app.py
git commit -m "feat: wire TaskStore into AssistantApp with deadline polling"
```

---

## Final Verification

- [ ] **Run complete test suite**

```
pytest tests/ -v
```
Expected: 138 passed, 0 failed

> Cumulative: 91 (baseline) + 2 (Task 1 config) + 19 (Task 2 store) + 23 (Task 3 agent) + 3 (Task 4 app) = 138

- [ ] **Verify TaskAgent loads via AgentRegistry**

```python
from pathlib import Path
from assistant_22b.agents.registry import AgentRegistry
agents_dir = Path("src/assistant_22b/agents")
reg = AgentRegistry(agents_dir)
matched = reg.route("할일 추가해줘")
print([a.agent_id for a in matched])  # should include "task"
```

- [ ] **Final commit if needed**

```bash
git add -p
git commit -m "feat: Phase B item 7 — Task Agent complete"
```
