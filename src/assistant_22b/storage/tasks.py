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
        blob = self._fernet.encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
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
                data = json.loads(self._fernet.decrypt(blob).decode("utf-8"))
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
        now = datetime.now()
        cutoff = now + timedelta(hours=hours)
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT blob FROM tasks ORDER BY id").fetchall()
        result = []
        for (blob,) in rows:
            try:
                data = json.loads(self._fernet.decrypt(blob).decode("utf-8"))
            except Exception:
                continue
            if data.get("status") != "open":
                continue
            due = data.get("due_date")
            if not due:
                continue
            try:
                due_dt = datetime.fromisoformat(due)
            except ValueError:
                continue
            if now <= due_dt <= cutoff:
                result.append(data)
        return result

    def _update_blob(self, task_id: str, changes: dict) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT id, blob FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                return False
            row_id, blob = row
            try:
                data = json.loads(self._fernet.decrypt(blob).decode("utf-8"))
            except Exception:
                return False
            data.update(changes)
            data["updated_at"] = datetime.now().isoformat()
            new_blob = self._fernet.encrypt(
                json.dumps(data, ensure_ascii=False).encode("utf-8")
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id    TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    blob       BLOB NOT NULL
                )
                """
            )

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
