"""User accounts + role/permission CRUD over SQLite — the RBAC store.

Roles and the permission catalog live in core.rbac; this module persists rows and
enforces store-level integrity: unique email, valid role, and never letting the
last active admin be removed, demoted, or deactivated (so the app can't lock
itself out of user management). A default admin is seeded on first use.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from .db import conn
from ..core import rbac

_DEFAULT_ADMIN = {"name": "admin", "email": "admin@kkel.com"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row(r) -> dict:
    d = dict(r)
    d["permissions"] = json.loads(d.get("permissions") or "[]")
    d["active"] = bool(d["active"])
    return d


# admins first, then by creation order — a stable, readable listing
_ORDER = "ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END, created_at"


def list_users() -> list[dict]:
    return [_row(r) for r in conn().execute(f"SELECT * FROM users {_ORDER}").fetchall()]


def get(uid: str) -> dict | None:
    r = conn().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return _row(r) if r else None


def get_by_email(email: str) -> dict | None:
    r = conn().execute("SELECT * FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
    return _row(r) if r else None


def count_active_admins(exclude: str | None = None) -> int:
    rows = conn().execute("SELECT id FROM users WHERE role='admin' AND active=1").fetchall()
    return sum(1 for r in rows if r["id"] != exclude)


def _validate_email(email: str) -> str:
    email = (email or "").strip()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError("Enter a valid email address.")
    return email


def create(name: str, email: str, role: str = "member", permissions=None) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Name is required.")
    email = _validate_email(email)
    if not rbac.is_role(role):
        raise ValueError("Role must be admin or member.")
    if get_by_email(email):
        raise ValueError("A user with that email already exists.")
    perms = rbac.clean_permissions(permissions) if permissions is not None \
        else rbac.default_permissions(role)
    uid, ts = uuid.uuid4().hex[:12], _now()
    conn().execute(
        "INSERT INTO users(id,name,email,role,permissions,active,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?)", (uid, name, email, role, json.dumps(perms), 1, ts, ts))
    conn().commit()
    return get(uid)


def update(uid: str, name=None, email=None, role=None, permissions=None, active=None) -> dict:
    u = get(uid)
    if not u:
        raise ValueError("User not found.")
    # last-admin protection: can't demote or deactivate the only admin left
    demoting = role is not None and role != "admin" and u["role"] == "admin"
    deactivating = active is False and u["role"] == "admin"
    if (demoting or deactivating) and count_active_admins(exclude=uid) == 0:
        raise ValueError("There must always be at least one active admin.")
    fields, vals = [], []
    if name is not None:
        if not name.strip():
            raise ValueError("Name cannot be empty.")
        fields.append("name=?"); vals.append(name.strip())
    if email is not None:
        email = _validate_email(email)
        other = get_by_email(email)
        if other and other["id"] != uid:
            raise ValueError("A user with that email already exists.")
        fields.append("email=?"); vals.append(email)
    if role is not None:
        if not rbac.is_role(role):
            raise ValueError("Role must be admin or member.")
        fields.append("role=?"); vals.append(role)
        if permissions is None:                       # role change -> reset to role defaults
            permissions = rbac.default_permissions(role)
    if permissions is not None:
        fields.append("permissions=?"); vals.append(json.dumps(rbac.clean_permissions(permissions)))
    if active is not None:
        fields.append("active=?"); vals.append(1 if active else 0)
    if not fields:
        return u
    fields.append("updated_at=?"); vals.append(_now())
    vals.append(uid)
    conn().execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", vals)
    conn().commit()
    return get(uid)


def delete(uid: str) -> bool:
    u = get(uid)
    if not u:
        return False
    if u["role"] == "admin" and count_active_admins(exclude=uid) == 0:
        raise ValueError("Cannot remove the last active admin.")
    conn().execute("DELETE FROM users WHERE id=?", (uid,))
    conn().commit()
    return True


def seed_default_admin() -> None:
    """Ensure at least one admin exists so the app is usable on first run."""
    if conn().execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return
    create(_DEFAULT_ADMIN["name"], _DEFAULT_ADMIN["email"], "admin")


def current_user() -> dict | None:
    """The operator the UI acts as. There is no login yet, so this is the first
    active admin (the seeded one). Centralized here so adding real auth later is
    a local change."""
    seed_default_admin()
    r = conn().execute(f"SELECT * FROM users WHERE active=1 {_ORDER} LIMIT 1").fetchone()
    return _row(r) if r else None
