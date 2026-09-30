"""SQLite-backed runs store for the standalone UI. Best-effort persistence for POST /run."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    cases_count INTEGER NOT NULL,
    "pass" INTEGER NOT NULL,
    fail INTEGER NOT NULL,
    provider TEXT NOT NULL,
    session_id TEXT NOT NULL
);
"""


def hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunsStore:
    def __init__(self, path: str | Path):
        self._path = str(path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def record_run(
        self,
        prompt: str,
        cases: list[dict[str, Any]],
        report: dict[str, Any],
        provider: str,
        session_id: str,
    ) -> int:
        row = (
            _utcnow_iso(),
            hash_prompt(prompt),
            len(cases),
            int(report.get("pass", 0)),
            int(report.get("fail", 0)),
            provider,
            session_id,
        )
        with self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO runs (ts, prompt_hash, cases_count, "pass", fail, provider, session_id) '
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                row,
            )
            return int(cur.lastrowid)

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                'SELECT id, ts, prompt_hash, cases_count, "pass", fail, provider, session_id '
                "FROM runs ORDER BY id DESC LIMIT ?",
                (int(limit),),
            )
            return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        with self._connect() as conn:
            (n,) = conn.execute("SELECT COUNT(*) FROM runs").fetchone()
            return int(n)
