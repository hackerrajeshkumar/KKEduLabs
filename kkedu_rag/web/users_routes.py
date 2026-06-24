"""User & role management API (RBAC).

Admins create users, assign a role (admin / member), tune per-user permissions,
and remove users. The store (storage.users) enforces integrity; these routes
surface its errors to the UI as 400s. Only an admin operator may mutate users
(403 otherwise). There is no login yet, so the operator is the acting admin
returned as `current` — see storage.users.current_user.
"""
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from ..storage import users as store
from ..core import rbac

router = APIRouter(prefix="/api")


class NewUser(BaseModel):
    name: str
    email: str
    role: str = "member"
    permissions: list[str] | None = None


class UserPatch(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None
    permissions: list[str] | None = None
    active: bool | None = None


def _deny_if_not_admin():
    """Return a 403 response unless the operator is an admin who may manage users."""
    cur = store.current_user()
    if not cur or cur["role"] != "admin" or "manage_users" not in cur["permissions"]:
        return JSONResponse({"error": "Admin access is required to manage users."},
                            status_code=403)
    return None


@router.get("/users")
async def list_users():
    """All users + the acting operator + RBAC metadata (roles, permission catalog)."""
    return JSONResponse({"users": store.list_users(),
                         "current": store.current_user(),
                         "rbac": rbac.catalog()})


@router.post("/users")
async def create_user(body: NewUser):
    if (deny := _deny_if_not_admin()):
        return deny
    try:
        u = store.create(body.name, body.email, body.role, body.permissions)
    except ValueError as err:
        return JSONResponse({"error": str(err)}, status_code=400)
    return JSONResponse({"user": u, "users": store.list_users()})


@router.patch("/users/{uid}")
async def update_user(uid: str, body: UserPatch):
    if (deny := _deny_if_not_admin()):
        return deny
    try:
        u = store.update(uid, **body.model_dump(exclude_unset=True))
    except ValueError as err:
        return JSONResponse({"error": str(err)}, status_code=400)
    return JSONResponse({"user": u, "users": store.list_users()})


@router.post("/users/{uid}/delete")
async def delete_user(uid: str):
    if (deny := _deny_if_not_admin()):
        return deny
    try:
        ok = store.delete(uid)
    except ValueError as err:
        return JSONResponse({"error": str(err)}, status_code=400)
    return JSONResponse({"deleted": ok, "users": store.list_users()})
