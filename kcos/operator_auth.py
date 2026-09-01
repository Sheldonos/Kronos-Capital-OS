from __future__ import annotations

import hmac


def normalized_host(host_header: str | None) -> str:
    raw = (host_header or "").strip().lower()
    if raw.startswith("[") and "]" in raw:
        return raw[1:raw.index("]")]
    if raw.count(":") == 1:
        return raw.rsplit(":", 1)[0]
    return raw


def is_loopback_host(host_header: str | None) -> bool:
    return normalized_host(host_header) in {"127.0.0.1", "localhost", "::1"}


def operator_authorized(host_header: str | None, provided_token: str | None, expected_token: str, require_remote_token: bool = True) -> bool:
    if not require_remote_token or is_loopback_host(host_header):
        return True
    return bool(provided_token and hmac.compare_digest(str(provided_token), str(expected_token)))
