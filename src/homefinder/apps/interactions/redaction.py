"""Shared redaction policy for persisted interaction diagnostics."""
from __future__ import annotations

import re
from typing import Any

REDACTED_DETAIL_VALUE = "[REDACTED]"

_CAMEL_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_KEY_CHARS = re.compile(r"[^a-z0-9]+")

SENSITIVE_DETAIL_KEYS = frozenset(
    {
        "2fa_code",
        "access_key",
        "access_token",
        "api_key",
        "auth_code",
        "auth_token",
        "authorization",
        "code",
        "credential",
        "credentials",
        "login_2fa_code",
        "login_code",
        "mfa_code",
        "one_time_code",
        "otp",
        "otp_code",
        "password",
        "password_hash",
        "private_key",
        "recovery_code",
        "refresh_token",
        "secret",
        "secret_key",
        "session_token",
        "session_token_hash",
        "token",
        "token_hash",
        "two_factor_code",
        "two_factor_token",
        "verification_code",
    }
)
SENSITIVE_KEY_MARKERS = ("authorization", "credential", "password", "passwd", "secret", "token")
SENSITIVE_CODE_CONTEXTS = ("2fa", "auth", "login", "mfa", "one_time", "otp", "recovery", "two_factor", "verification")


def should_redact_activity_detail_key(key: Any) -> bool:
    """Return whether an activity-log detail key should never persist raw values."""

    normalized_key = normalize_activity_detail_key(key)
    if not normalized_key:
        return False
    if normalized_key in SENSITIVE_DETAIL_KEYS:
        return True
    if any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
        return True
    return normalized_key.endswith("_code") and any(context in normalized_key for context in SENSITIVE_CODE_CONTEXTS)


def normalize_activity_detail_key(key: Any) -> str:
    try:
        key_text = str(key)
    except Exception:
        return ""

    key_with_boundaries = _CAMEL_CASE_BOUNDARY.sub("_", key_text)
    normalized_key = _NON_KEY_CHARS.sub("_", key_with_boundaries.lower())
    return normalized_key.strip("_")
