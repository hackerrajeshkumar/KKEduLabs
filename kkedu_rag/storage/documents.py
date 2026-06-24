"""Persisted document text, so the index survives restarts.

On upload we save the raw text here; on boot we re-add every saved document to
the in-memory store (re-embedding via Ollama). Removing a document deletes it
from this table too, so it won't come back on the next restart.
"""
from __future__ import annotations
from datetime import datetime
from .db import conn


def save(source: str, content: str) -> None:
    """Persist (or replace) one document's raw text."""
    conn().execute("INSERT OR REPLACE INTO documents(source,content,created_at) "
                   "VALUES(?,?,?)", (source, content, datetime.now().isoformat(timespec="seconds")))
    conn().commit()


def delete(source: str) -> None:
    """Forget a document so it is not restored on the next boot."""
    conn().execute("DELETE FROM documents WHERE source=?", (source,))
    conn().commit()


def all_documents() -> list[tuple[str, str]]:
    """Every persisted (source, content) pair, oldest first — for boot restore."""
    rows = conn().execute("SELECT source,content FROM documents ORDER BY created_at").fetchall()
    return [(r["source"], r["content"]) for r in rows]
