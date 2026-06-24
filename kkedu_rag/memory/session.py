"""Conversation memory: the SDK SQLiteSession that persists turns across runs.

This module owns where/how the session is opened (db file + conversation id from
config). The answerer reads/writes turns through it automatically; the pipeline
also pops/re-adds the last assistant turn when the verifier replaces a draft, so
stored history always matches what the user saw.
"""
from __future__ import annotations
from agents import SQLiteSession
from ..core.config import MEMORY_DB, SESSION_ID


def open_session(session_id: str = SESSION_ID, db_path: str = MEMORY_DB) -> SQLiteSession:
    """Open (or create) the persistent conversation session backing memory."""
    return SQLiteSession(session_id, db_path)
