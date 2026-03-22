# src/assistant_22b/security/gate4_logger.py
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

from assistant_22b.pipeline.context import PipelineContext


class Gate4Logger:
    """Appends encrypted audit records to a local SQLite database.

    Schema: audit_log(id INTEGER PK, created_at TEXT, blob BLOB)
    Each blob is a Fernet-encrypted JSON payload containing the full audit record.
    created_at is stored as plaintext for time-based filtering.
    """

    def __init__(self, db_path: Path, key_path: Path) -> None:
        self._db_path = db_path
        self._key_path = key_path
        self._fernet = self._load_or_create_key()
        self._init_db()

    def _load_or_create_key(self) -> Fernet:
        if self._key_path.exists():
            key = self._key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self._key_path.parent.mkdir(parents=True, exist_ok=True)
            self._key_path.write_bytes(key)
        return Fernet(key)

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT    NOT NULL,
                    blob       BLOB    NOT NULL
                )
                """
            )

    def log(self, context: PipelineContext) -> None:
        """Encrypt and persist the audit record. Never raises."""
        try:
            record = {
                "request_id": context.request_id,
                "input_hash": hashlib.sha256(
                    context.input_text.encode("utf-8")
                ).hexdigest(),
                "sensitivity": context.sensitivity,
                "agents_used": [r.agent_id for r in context.agent_results],
                "gate_log": [
                    {
                        "gate": g.gate,
                        "passed": g.passed,
                        "timestamp": g.timestamp.isoformat(),
                        "notes": g.notes,
                    }
                    for g in context.gate_log
                ],
                "result_summaries": [
                    {
                        "agent_id": r.agent_id,
                        "citations": r.citations,
                        "verified": r.verified,
                        "error": r.error,
                    }
                    for r in context.agent_results
                ],
                "external_sent": False,
            }
            payload = json.dumps(record, ensure_ascii=False, default=str).encode("utf-8")
            encrypted = self._fernet.encrypt(payload)
            now = datetime.now().isoformat()
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO audit_log (created_at, blob) VALUES (?, ?)",
                    (now, encrypted),
                )
        except Exception as exc:
            print(f"[Gate4] Audit log failed: {exc}", file=sys.stderr)

    def read_all(self) -> list[dict]:
        """Decrypt and return all audit records. For testing and audit review."""
        results = []
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT blob FROM audit_log ORDER BY id"
            ).fetchall()
        for (blob,) in rows:
            try:
                payload = self._fernet.decrypt(blob)
                results.append(json.loads(payload.decode("utf-8")))
            except Exception:
                results.append({"error": "decryption_failed"})
        return results
