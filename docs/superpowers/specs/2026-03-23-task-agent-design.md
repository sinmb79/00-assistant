# Task Agent — Design Spec

**Date:** 2026-03-23
**Phase:** B (item 7)
**Status:** Approved

---

## Overview

Add a `TaskAgent` to 22B Assistant for todo/schedule management. Fully local, rule-based (no LLM), encrypted SQLite storage. Follows the existing `BaseAgent` + `manifest.json` pattern.

---

## Architecture

### New files

```
src/assistant_22b/
├── storage/
│   └── tasks.py                  # TaskStore — Fernet-encrypted SQLite
└── agents/
    └── task/
        ├── __init__.py
        ├── manifest.json
        └── agent.py               # TaskAgent(BaseAgent)

tests/
├── test_task_store.py
└── test_task_agent.py
```

### Runtime data (`~/.22b-assistant/`)

| File | Purpose |
|---|---|
| `db/tasks.db` | Encrypted task rows |
| `.tasks_key` | Fernet key for tasks.db |

### Config change

Add field to `AssistantConfig` dataclass in `config.py`:

```python
task_check_interval_minutes: int = 60
```

`ConfigManager._load()` filters by `{f.name for f in fields(AssistantConfig)}`, so the field must exist in the dataclass to be loaded from `config.json`.

### Notification polling

`AssistantApp` uses `root.after(interval_ms, callback)` (tkinter main-loop safe) to periodically call `TaskStore.query_due_soon()`. No background threads needed. Result shown as tray notification if any tasks are due within 24 hours.

---

## Data Model

### Physical SQLite schema (`tasks.db`)

```sql
CREATE TABLE tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT NOT NULL,   -- UUID4, plaintext for direct lookup
    created_at TEXT NOT NULL,   -- plaintext for range queries
    blob       BLOB NOT NULL    -- Fernet-encrypted JSON payload
)
```

### Encrypted JSON payload (inside `blob`)

```json
{
  "task_id":    "uuid4-string",
  "title":      "보고서 작성",
  "due_date":   "2026-03-25T17:00",
  "priority":   2,
  "status":     "open",
  "created_at": "2026-03-23T09:00:00",
  "updated_at": "2026-03-23T09:00:00"
}
```

Fields:
- `due_date`: ISO 8601 (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM`), nullable
- `priority`: `1`=high, `2`=normal, `3`=low
- `status`: `"open"` | `"done"`

`task_id` is kept as a plaintext column so DONE/DELETE/UPDATE operations can locate a row without decrypting every blob (same reason `ConversationStore` keeps `session_id` plaintext).

Key file auto-created on first use (same pattern as `Gate4Logger` and `ConversationStore`).

---

## Routing: Two-stage

1. **`AgentRegistry.route(text)`** — matches `triggers` in `manifest.json` against user input to select `TaskAgent`.
2. **`TaskAgent.process(context)`** — further classifies intent from `context.input_text` using a separate keyword set.

These two keyword sets are **independent**. `triggers` is for agent selection; intent keywords are for action dispatch inside the agent.

### manifest.json

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

### Intent classification (inside `process()`)

| Intent | Trigger keywords | Action |
|---|---|---|
| ADD | 추가, 등록, 할일, 해야, 만들어 | Insert new task |
| LIST | 오늘, 이번 주, 목록, 뭐 해야, 알려줘 | Query tasks by filter |
| DONE | 완료, 다 했어, 끝났어, 했어 | Set status = 'done' |
| DELETE | 삭제, 취소, 지워 | Remove task |
| UPDATE | 수정, 바꿔, 변경 | Update title / due_date / priority |
| UNKNOWN | (no match) | Return clarification prompt |

Classification is case-insensitive substring match.

---

## Error Handling

| Situation | Behavior |
|---|---|
| Intent not recognized | `AgentResult(output="무슨 일정 작업을 원하시나요? (추가/조회/완료/삭제)")` |
| `due_date` parse failure | Save task without due_date; warning appended to `output` |
| TaskStore access failure | `AgentResult(error="TaskStore 접근 오류: {exc}")` — pipeline continues |
| Corrupt blob (wrong key) | Log and skip row; do not raise — same pattern as `ConversationStore` |

`AgentResult.error` is `str | None` (not bool). Error string is shown to user via existing `app.py` `if result.error:` branch.

---

## Testing

### `test_task_store.py`
- Create / read / update / delete a task row
- Encryption roundtrip (blob unreadable without key)
- Key file auto-created when missing (same as `test_key_created_in_parent_dir` in gate4 tests)
- Corrupt/wrong-key blob handled gracefully (row skipped, no exception)
- Query by status (`open` only)
- Query by due_date range (today, this week)
- TaskStore access failure propagates as error string to caller

### `test_task_agent.py`
- ADD: title extracted, task created, `AgentResult.output` confirms
- LIST: returns open tasks filtered by "오늘" / "이번 주"
- DONE: marks matching task as done
- DELETE: removes matching task
- UPDATE: updates title / due_date / priority
- UNKNOWN: returns clarification message
- TaskStore failure: `AgentResult.error` is a non-empty string

All 91 existing tests must continue to pass.

---

## Design Constraints

- No LLM calls — rule-based only
- Local-only — no network calls, no sync
- Fernet encryption — same approach as `ConversationStore` and `Gate4Logger`
- `BaseAgent` pattern — `manifest.json` auto-loaded by `AgentRegistry`
- P1 code untouched
