"""Encrypted SQLite conversation history store."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet


@dataclass
class ConversationTurn:
    role: str       # "user" | "assistant"
    content: str
    timestamp: datetime


class ConversationStore:
    """Appends and retrieves encrypted conversation turns in SQLite."""

    def __init__(self, db_path: Path, key_path: Path) -> None:
        self._db_path = db_path
        self._fernet = self._load_or_create_key(key_path)
        self._init_db()

    # ------------------------------------------------------------------
    def append(self, session_id: str, turn: ConversationTurn) -> None:
        record = {
            "role": turn.role,
            "content": turn.content,
            "timestamp": turn.timestamp.isoformat(),
        }
        encrypted = self._fernet.encrypt(
            json.dumps(record, ensure_ascii=False).encode("utf-8")
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO conversations (session_id, created_at, blob) VALUES (?, ?, ?)",
                (session_id, turn.timestamp.isoformat(), encrypted),
            )

    def get_session(self, session_id: str) -> list[ConversationTurn]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT blob FROM conversations WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        turns: list[ConversationTurn] = []
        for (blob,) in rows:
            try:
                data = json.loads(self._fernet.decrypt(blob).decode("utf-8"))
                turns.append(
                    ConversationTurn(
                        role=data["role"],
                        content=data["content"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                    )
                )
            except Exception:
                pass
        return turns

    # ------------------------------------------------------------------
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
                CREATE TABLE IF NOT EXISTS conversations (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT    NOT NULL,
                    created_at TEXT    NOT NULL,
                    blob       BLOB    NOT NULL
                )
                """
            )
