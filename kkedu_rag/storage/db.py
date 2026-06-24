"""SQLite connection + schema for chat threads and persisted documents.

One file-backed DB (rag.db). The schema is created on first connect. Threads
hold metadata only — their messages live in the SDK session store keyed by the
same thread id. Documents store raw text so they can be re-embedded on boot.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB_PATH = "rag.db"
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    source     TEXT PRIMARY KEY,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    role        TEXT NOT NULL DEFAULT 'member',
    permissions TEXT NOT NULL DEFAULT '[]',   -- JSON array of permission keys
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def conn() -> sqlite3.Connection:
    """The shared connection (created + schema-initialized on first use)."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn
