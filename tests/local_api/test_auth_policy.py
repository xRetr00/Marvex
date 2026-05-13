from __future__ import annotations

from packages.contracts import ErrorCode, ErrorEnvelope


def test_valid_bearer_token_is_accepted():
    from packages.local_api.auth_policy import validate_local_bearer_token

    error = validate_local_bearer_token(
        authorization_header="Bearer fake-local-token",
        expected_token="fake-local-token",
        trace_id="trace-auth-test",
    )

    assert error is None


def test_missing_bearer_token_returns_safe_auth_error():
    from packages.local_api.auth_policy import validate_local_bearer_token

    error = validate_local_bearer_token(
        authorization_header=None,
        expected_token="fake-local-token",
        trace_id="trace-auth-test",
    )

    assert isinstance(error, ErrorEnvelope)
    assert error.schema_version == "0.1.1-draft"
    assert error.trace_id == "trace-auth-test"
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert error.message == "Local API authentication required."
    assert error.source == "local_api"
    assert error.details == {
        "header": "Authorization",
        "reason": "missing",
        "scheme": "Bearer",
    }
    assert "fake-local-token" not in error.model_dump_json()


def test_wrong_bearer_token_returns_safe_auth_error_without_token_values():
    from packages.local_api.auth_policy import validate_local_bearer_token

    error = validate_local_bearer_token(
        authorization_header="Bearer wrong-token",
        expected_token="fake-local-token",
        trace_id="trace-auth-test",
    )

    assert isinstance(error, ErrorEnvelope)
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert error.details == {
        "header": "Authorization",
        "reason": "invalid",
        "scheme": "Bearer",
    }
    serialized = error.model_dump_json()
    assert "wrong-token" not in serialized
    assert "fake-local-token" not in serialized


def test_malformed_authorization_header_returns_safe_auth_error():
    from packages.local_api.auth_policy import validate_local_bearer_token

    error = validate_local_bearer_token(
        authorization_header="Token fake-local-token",
        expected_token="fake-local-token",
        trace_id="trace-auth-test",
    )

    assert isinstance(error, ErrorEnvelope)
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert error.details == {
        "header": "Authorization",
        "reason": "invalid",
        "scheme": "Bearer",
    }
    assert "fake-local-token" not in error.model_dump_json()


def test_unconfigured_expected_token_fails_closed_without_secret_details():
    from packages.local_api.auth_policy import validate_local_bearer_token

    error = validate_local_bearer_token(
        authorization_header="Bearer fake-local-token",
        expected_token="",
        trace_id="trace-auth-test",
    )

    assert isinstance(error, ErrorEnvelope)
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert error.details == {
        "header": "Authorization",
        "reason": "unconfigured",
        "scheme": "Bearer",
    }
    assert "fake-local-token" not in error.model_dump_json()
