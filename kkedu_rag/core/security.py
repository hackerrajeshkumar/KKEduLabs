"""Password hashing — salted PBKDF2-HMAC-SHA256, standard library only.

Stored format: ``pbkdf2$<iterations>$<salt_hex>$<hash_hex>``. Verification is
constant-time. No third-party crypto dependency is introduced.
"""
from __future__ import annotations
import hashlib
import hmac
import secrets

_ALGO = "sha256"
_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False
