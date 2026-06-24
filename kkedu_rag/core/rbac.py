"""Role-based access control model: roles, the permission catalog, and the
default permissions per role.

Pure data + helpers — no framework, no I/O — so the storage layer, the API, and
the UI all share one source of truth. Roles are intentionally just two (admin /
member); fine-grained capability is expressed through the permission set, which
an admin can tune per user.
"""
from __future__ import annotations

ROLES = ("admin", "member")

# capability key -> human label (rendered as toggles in the Users settings page)
PERMISSIONS: dict[str, str] = {
    "ask_questions": "Ask questions (chat)",
    "view_documents": "View & search documents",
    "upload_documents": "Upload & index documents",
    "delete_documents": "Remove documents",
    "export_conversations": "Export conversations",
    "manage_settings": "Manage system settings",
    "manage_users": "Manage users & roles",
}

# what each role can do out of the box; admins get the full catalog
ROLE_DEFAULTS: dict[str, list[str]] = {
    "admin": list(PERMISSIONS),
    "member": ["ask_questions", "view_documents", "export_conversations"],
}


def is_role(role: str) -> bool:
    return role in ROLES


def default_permissions(role: str) -> list[str]:
    return list(ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["member"]))


def clean_permissions(perms) -> list[str]:
    """Keep only known permission keys, de-duplicated, in catalog order."""
    chosen = {p for p in (perms or []) if p in PERMISSIONS}
    return [k for k in PERMISSIONS if k in chosen]


def catalog() -> dict:
    """RBAC metadata for the UI: roles, the permission catalog, role defaults."""
    return {"roles": list(ROLES), "permissions": PERMISSIONS, "role_defaults": ROLE_DEFAULTS}
