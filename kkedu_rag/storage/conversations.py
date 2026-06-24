"""Chat-thread metadata CRUD (titles + timestamps) over SQLite.

Each thread's id doubles as the SDK session id, so messages are fetched from the
session store, not here. A thread's title is derived from its first question.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from .db import conn


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create(title: str = "New chat") -> str:
    """Create a thread, returning its new id (also used as the session id)."""
    tid = uuid.uuid4().hex[:12]
    ts = _now()
    conn().execute("INSERT INTO conversations(id,title,created_at,updated_at) "
                   "VALUES(?,?,?,?)", (tid, title[:80], ts, ts))
    conn().commit()
    return tid


def touch(tid: str, title: str | None = None) -> None:
    """Bump updated_at (and optionally set the title) when a thread gets activity."""
    if title is not None:
        conn().execute("UPDATE conversations SET title=?, updated_at=? WHERE id=?",
                       (title[:80], _now(), tid))
    else:
        conn().execute("UPDATE conversations SET updated_at=? WHERE id=?", (_now(), tid))
    conn().commit()


def list_all() -> list[dict]:
    """All threads, most-recently-updated first."""
    rows = conn().execute("SELECT id,title,created_at,updated_at FROM conversations "
                          "ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def get(tid: str) -> dict | None:
    row = conn().execute("SELECT id,title,created_at,updated_at FROM conversations "
                         "WHERE id=?", (tid,)).fetchone()
    return dict(row) if row else None


def delete(tid: str) -> bool:
    cur = conn().execute("DELETE FROM conversations WHERE id=?", (tid,))
    conn().commit()
    return cur.rowcount > 0
