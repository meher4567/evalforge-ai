from __future__ import annotations

import hashlib

from app.core.config import get_settings
from app.services.authentication import hash_token


def test_token_fingerprint_is_keyed_blake2b(monkeypatch):
    monkeypatch.setenv("EVALFORGE_AUTH_TOKEN_PEPPER", "test-token-pepper")
    get_settings.cache_clear()
    try:
        pepper_key = hashlib.blake2b(b"test-token-pepper", digest_size=32).digest()
        expected = hashlib.blake2b(
            b"efs_example-token",
            key=pepper_key,
            digest_size=32,
        ).hexdigest()

        assert hash_token("efs_example-token") == expected
        assert len(expected) == 64
        assert hash_token("efs_different-token") != expected
    finally:
        get_settings.cache_clear()
