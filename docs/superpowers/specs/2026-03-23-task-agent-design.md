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
        ├── role_prompt.txt
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

### Notification polling

`AssistantApp` checks for upcoming deadlines on a configurable interval.
Config key: `task_check_interval_minutes` (default: 60).
User can change this in `~/.22b-assistant/config.json`.

---

## Data Model

```sql
CREATE TABLE tasks (
    id         TEXT PRIMARY KEY,    -- UUID4
    title      TEXT NOT NULL,
    due_date   TEXT,                -- ISO 8601: YYYY-MM-DD or YYYY-MM-DDTHH:MM
    priority   INTEGER DEFAULT 2,   -- 1=high  2=normal  3=low
    status     TEXT DEFAULT 'open', -- 'open' | 'done'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

Each row is serialized to JSON, encrypted with Fernet, stored as a single blob column — same pattern as `ConversationStore`.

---

## TaskAgent Intent Classification

`TaskAgent.process()` classifies intent by keyword matching on `context.input_text`, then calls the appropriate `TaskStore` method.

| Intent | Trigger keywords (Korean) | Action |
|---|---|---|
| ADD | 추가, 등록, 할일, 해야, 만들어 | Insert new task |
| LIST | 오늘, 이번 주, 목록, 뭐 해야, 알려줘 | Query tasks by filter |
| DONE | 완료, 다 했어, 끝났어, 했어 | Set status = 'done' |
| DELETE | 삭제, 취소, 지워 | Remove task |
| UPDATE | 수정, 바꿔, 변경 | Update title / due_date / priority |
| UNKNOWN | (no match) | Return clarification prompt |

Classification is case-insensitive, checks for substring presence.

---

## Error Handling

| Situation | Behavior |
|---|---|
| Intent not recognized | Return `AgentResult` with message: "무슨 일정 작업을 원하시나요? (추가/조회/완료/삭제)" |
| `due_date` parse failure | Save task without due_date; include warning in output |
| TaskStore access failure | Return `AgentResult` with `error=True`; pipeline continues |

Errors do not propagate exceptions — `AgentResult` carries the error signal.

---

## Testing

### `test_task_store.py`
- Create / read / update / delete a task row
- Encryption roundtrip (data unreadable without key)
- Query by status (`open` only)
- Query by due_date range (today, this week)

### `test_task_agent.py`
- Each intent keyword triggers correct action
- ADD: title extracted from text, task created
- LIST: returns open tasks filtered by "오늘" / "이번 주"
- DONE: marks matching task as done
- DELETE: removes matching task
- UNKNOWN: returns clarification message

All 91 existing tests must continue to pass.

---

## Design Constraints

- No LLM calls — rule-based only (Phase A/B constraint)
- Local-only — no network calls, no sync
- Fernet encryption — same approach as `ConversationStore` and `Gate4Logger`
- `BaseAgent` pattern — `manifest.json` auto-loaded by `AgentRegistry`
- P1 code untouched
