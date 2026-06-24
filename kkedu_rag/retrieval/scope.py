"""Per-turn document scope: which files the current question may draw from.

The answerer's tool signature is fixed by the SDK, so it can't take a 'sources'
argument. Instead the request handler sets the active scope here before running
the turn, and the tool reads it. A ContextVar keeps concurrent requests isolated.
"""
from __future__ import annotations
from contextvars import ContextVar

_active: ContextVar[list[str] | None] = ContextVar("active_sources", default=None)


def set_sources(sources: list[str] | None) -> None:
    """Set the active document scope for the current turn (None/empty = all)."""
    _active.set(sources or None)


def get_sources() -> list[str] | None:
    """The files the current turn is scoped to, or None for all documents."""
    return _active.get()
