"""Session authentication: verify credentials, mint an in-process session token,
and resolve the current user from the request cookie.

Sessions live in memory (reset on restart — users just sign in again), so there
is no external session-store dependency. Passwords are checked in storage.users
via core.security. The acting user is now whoever holds a valid session cookie —
this replaces the old "always the seeded admin" behaviour.
"""
from __future__ import annotations
import secrets
from fastapi import Request
from ..storage import users as store

COOKIE = "kkedu_session"
_SESSIONS: dict[str, str] = {}        # session token -> user id


def login(email: str, password: str):
    """Return (user, token) on success, (None, None) otherwise."""
    user = store.verify(email, password)
    if not user:
        return None, None
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = user["id"]
    return user, token


def logout(token: str | None) -> None:
    if token:
        _SESSIONS.pop(token, None)


def user_for_request(request: Request) -> dict | None:
    """The signed-in user for this request, or None if unauthenticated."""
    token = request.cookies.get(COOKIE)
    uid = _SESSIONS.get(token) if token else None
    if not uid:
        return None
    user = store.get(uid)
    return user if user and user.get("active") else None
