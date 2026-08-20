from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from app.core.config import get_settings

LOCAL_PROVIDER_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"}
)


def validate_provider_url(base_url: str, *, allow_local: bool = False) -> str:
    """Reject credential-bearing, unexpected, and private provider endpoints."""
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Provider base_url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("Provider base_url must not contain credentials")

    host = parsed.hostname.lower().rstrip(".")
    settings = get_settings()
    allowed_hosts = {
        item.strip().lower().rstrip(".")
        for item in getattr(settings, "llm_allowed_hosts", "api.openai.com,api.groq.com").split(",")
        if item.strip()
    }

    if host in allowed_hosts:
        if parsed.scheme != "https":
            raise ValueError("Remote provider base_url must use HTTPS")
        return base_url.rstrip("/")

    if allow_local and host in LOCAL_PROVIDER_HOSTS:
        return base_url.rstrip("/")

    if getattr(settings, "allow_private_provider_urls", False):
        return base_url.rstrip("/")

    try:
        is_private_ip = not ipaddress.ip_address(host).is_global
    except ValueError:
        is_private_ip = False
    if is_private_ip:
        raise ValueError("Private provider URLs are disabled")

    raise ValueError(
        f"Provider host {host!r} is not allowed; configure EVALFORGE_LLM_ALLOWED_HOSTS"
    )


def validate_api_key_environment(name: str) -> str:
    settings = get_settings()
    allowed_names = {
        item.strip()
        for item in getattr(
            settings, "llm_api_key_env_allowlist", "OPENAI_API_KEY,GROQ_API_KEY"
        ).split(",")
        if item.strip()
    }
    if name not in allowed_names:
        raise ValueError(f"API key environment variable {name!r} is not allowed")
    return name
