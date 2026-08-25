from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.base import utc_now

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return "$".join(
        (
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            _encode(salt),
            _encode(digest),
        )
    )


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        expected_digest = _decode(expected)
        digest = hashlib.scrypt(
            password.encode(),
            salt=_decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_digest),
        )
        return hmac.compare_digest(digest, expected_digest)
    except (AttributeError, ValueError, TypeError):
        return False


def new_session_token() -> tuple[str, str, datetime]:
    token = f"efs_{secrets.token_urlsafe(32)}"
    expires_at = utc_now() + timedelta(hours=get_settings().session_ttl_hours)
    return token, hash_token(token), expires_at


def new_api_key() -> tuple[str, str, str]:
    secret = secrets.token_urlsafe(32)
    prefix = secret[:8]
    token = f"efk_{prefix}_{secret}"
    return token, prefix, hash_token(token)


def hash_token(token: str) -> str:
    pepper_key = hashlib.blake2b(
        get_settings().auth_token_pepper.encode(),
        digest_size=32,
    ).digest()
    return hashlib.blake2b(
        token.encode(),
        key=pepper_key,
        digest_size=32,
    ).hexdigest()


def is_expired(value: datetime | None) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value <= utc_now()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
