"""Password hashing + API key utilities (stdlib only — no new deps).

Passwords are stored as PBKDF2-HMAC-SHA256 with a random per-user salt;
API keys are 32-byte hex tokens stored hashed (so a DB leak doesn't expose
usable keys).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    )
    return f"pbkdf2${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest_hex = stored.split("$", 3)
        if scheme != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def generate_api_key() -> str:
    """A fresh API key (client-facing, shown once)."""
    return secrets.token_hex(32)


def hash_api_key(api_key: str) -> str:
    """Storage form of an API key (SHA-256, no salt needed for high-entropy keys)."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
