from __future__ import annotations

import hmac

from packages.contracts import ErrorCode, ErrorEnvelope


SCHEMA_VERSION = "0.1.1-draft"
LOCAL_AUTH_HEADER = "Authorization"
LOCAL_AUTH_SCHEME = "Bearer"


def validate_local_bearer_token(
    *,
    authorization_header: str | None,
    expected_token: str,
    trace_id: str,
) -> ErrorEnvelope | None:
    if not expected_token.strip():
        return _auth_error(trace_id=trace_id, reason="unconfigured")
    if authorization_header is None or not authorization_header.strip():
        return _auth_error(trace_id=trace_id, reason="missing")

    parts = authorization_header.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != LOCAL_AUTH_SCHEME.lower():
        return _auth_error(trace_id=trace_id, reason="invalid")

    provided_token = parts[1]
    if not hmac.compare_digest(provided_token, expected_token):
        return _auth_error(trace_id=trace_id, reason="invalid")

    return None


def _auth_error(*, trace_id: str, reason: str) -> ErrorEnvelope:
    return ErrorEnvelope(
        schema_version=SCHEMA_VERSION,
        trace_id=trace_id,
        error_id="local-api-auth-required",
        code=ErrorCode.AUTH_REQUIRED,
        message="Local API authentication required.",
        recoverable=False,
        source="local_api",
        details={
            "header": LOCAL_AUTH_HEADER,
            "scheme": LOCAL_AUTH_SCHEME,
            "reason": reason,
        },
    )
