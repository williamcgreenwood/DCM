"""HAR security: count and strip secrets. Never persist auth material."""

from __future__ import annotations

from typing import Any

SECRET_HEADER_KEYS = frozenset({
    "cookie",
    "set-cookie",
    "authorization",
    "proxy-authorization",
    "x-csrf-token",
    "x-xsrf-token",
    "csrf-token",
    "x-access-token",
    "x-refresh-token",
    "x-session-id",
    "x-device-id",
    "x-api-key",
})

SECRET_JSON_KEYS = frozenset({
    "cookie",
    "authorization",
    "set-cookie",
    "csrf",
    "csrftoken",
    "access_token",
    "refresh_token",
    "accesstoken",
    "refreshtoken",
    "session_id",
    "sessionid",
    "device_id",
    "deviceid",
    "account_id",
    "accountid",
    "password",
    "secret",
})

DENY_PATH_FRAGMENTS = (
    "/auth",
    "/login",
    "/logout",
    "/session",
    "/oauth",
    "/users/me",
    "/wallet",
    "/stripe",
    "/checkout",
    "/billing",
    "/entries",
    "/my-entries",
    "/profile",
    "/account",
)

ALLOW_HOST_FRAGMENTS = (
    "prizepicks.com",
    "outlier.bet",
    "outlier.com",
    "api.outlier",
)

SAFE_HEADER_NAMES = frozenset({"content-type", "content-encoding", "accept"})


def _is_secret_header(name: str) -> bool:
    return name.strip().lower() in SECRET_HEADER_KEYS


def count_secrets(value: Any, *, acc: int = 0) -> int:
    if isinstance(value, dict):
        for k, v in value.items():
            key = str(k).strip().lower()
            if key in SECRET_JSON_KEYS or _is_secret_header(key):
                acc += 1
            acc = count_secrets(v, acc=acc)
        return acc
    if isinstance(value, list):
        for item in value:
            acc = count_secrets(item, acc=acc)
        return acc
    if isinstance(value, str):
        lower = value.lower()
        for token in ("bearer ", "set-cookie:", "authorization:"):
            if token in lower:
                acc += 1
        return acc
    return acc


def redact_headers(headers: Any) -> tuple[list[dict[str, str]], int]:
    """Keep only non-secret, allowlisted header names. Never keep cookie/auth values."""
    safe: list[dict[str, str]] = []
    n = 0
    if not isinstance(headers, list):
        return safe, n
    for h in headers:
        if not isinstance(h, dict):
            continue
        name = str(h.get("name") or h.get("key") or "")
        lower = name.strip().lower()
        if _is_secret_header(name):
            n += 1
            continue
        if lower in SAFE_HEADER_NAMES:
            safe.append({"name": name, "value": str(h.get("value", ""))[:120]})
    return safe, n


def url_denied(url: str) -> bool:
    lower = url.lower()
    return any(frag in lower for frag in DENY_PATH_FRAGMENTS)


def url_allowlisted(url: str) -> bool:
    if url_denied(url):
        return False
    lower = url.lower()
    return any(frag in lower for frag in ALLOW_HOST_FRAGMENTS)
