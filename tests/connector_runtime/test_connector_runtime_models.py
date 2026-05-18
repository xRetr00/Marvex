from datetime import UTC, datetime

from pydantic import ValidationError


def test_connector_manifests_cover_required_account_categories_without_actions():
    from packages.connector_runtime import ConnectorCategory, default_connector_manifests

    manifests = default_connector_manifests()
    categories = {manifest.category for manifest in manifests}

    assert categories == {
        ConnectorCategory.GMAIL,
        ConnectorCategory.GOOGLE_CALENDAR,
        ConnectorCategory.GOOGLE_DRIVE,
        ConnectorCategory.GITHUB,
        ConnectorCategory.SLACK,
        ConnectorCategory.NOTION,
        ConnectorCategory.GENERIC_OAUTH,
    }
    assert all(manifest.account_action_allowed is False for manifest in manifests)
    assert all(manifest.auto_fetch_default_enabled is False for manifest in manifests)


def test_oauth_connection_projection_never_exposes_tokens_or_secrets():
    from packages.connector_runtime import (
        ConnectorCategory,
        ConnectorRef,
        ConnectorScope,
        OAuthConnectionRef,
        OAuthConnectionStatus,
    )

    connection = OAuthConnectionRef(
        connector_ref=ConnectorRef(connector_id="github-primary", category=ConnectorCategory.GITHUB),
        connection_id="oauth-github-1",
        account_label="xretro GitHub",
        status=OAuthConnectionStatus.CONNECTED,
        granted_scopes=(ConnectorScope(name="repo:read", purpose="Read repository metadata"),),
        token_storage="connector_auth_backend",
        connected_at=datetime(2026, 5, 18, tzinfo=UTC),
        expires_at=None,
        raw_token_persisted=False,
    )

    projection = connection.safe_projection()
    serialized = repr(projection).lower()
    assert projection["raw_token_persisted"] is False
    assert projection["token_storage"] == "connector_auth_backend"
    assert "secret" not in serialized
    assert "bearer" not in serialized
    assert "access_token" not in serialized


def test_connector_sync_request_requires_permission_and_blocks_hidden_autofetch():
    from packages.connector_runtime import (
        ConnectorCategory,
        ConnectorPermissionDecision,
        ConnectorRef,
        ConnectorSyncRequest,
        SourceSyncMode,
    )

    connector_ref = ConnectorRef(connector_id="gmail-primary", category=ConnectorCategory.GMAIL)

    with pytest_raises_validation():
        ConnectorSyncRequest(
            request_id="sync-1",
            connector_ref=connector_ref,
            sync_mode=SourceSyncMode.SCHEDULED_AUTO_FETCH,
            permission_decision=ConnectorPermissionDecision.DENIED,
            requested_at=datetime(2026, 5, 18, tzinfo=UTC),
            raw_credentials_persisted=False,
        )

    request = ConnectorSyncRequest(
        request_id="sync-2",
        connector_ref=connector_ref,
        sync_mode=SourceSyncMode.SCHEDULED_AUTO_FETCH,
        permission_decision=ConnectorPermissionDecision.APPROVED,
        requested_at=datetime(2026, 5, 18, tzinfo=UTC),
        raw_credentials_persisted=False,
    )
    assert request.safe_projection()["raw_credentials_persisted"] is False


def test_autofetch_policy_is_disabled_by_default_and_summaries_are_audit_safe():
    from packages.connector_runtime import AutoFetchPolicy, AutoFetchRunSummary, ConnectorCategory, ConnectorRef

    connector_ref = ConnectorRef(connector_id="slack-primary", category=ConnectorCategory.SLACK)
    policy = AutoFetchPolicy.default_for_connector(connector_ref)

    assert policy.control_state == "disabled"
    assert policy.connector_enabled is False
    assert policy.source_enabled is False
    assert policy.safe_projection()["control_plane_toggle_allowed"] is True

    summary = AutoFetchRunSummary(
        run_id="run-1",
        connector_ref=connector_ref,
        started_at=datetime(2026, 5, 18, tzinfo=UTC),
        completed_at=datetime(2026, 5, 18, 0, 1, tzinfo=UTC),
        status="completed",
        documents_seen=3,
        documents_canonicalized=2,
        chunks_created=5,
        raw_payload_persisted=False,
    )
    serialized = repr(summary.safe_projection()).lower()
    assert "token" not in serialized
    assert "raw_payload" in serialized
    assert summary.safe_projection()["raw_payload_persisted"] is False


def test_authlib_adapter_imports_real_oauth_library_without_token_fetch():
    from packages.adapters.connectors.authlib_oauth import AuthlibOAuthBackend

    backend = AuthlibOAuthBackend()
    proof = backend.safe_import_probe()

    assert proof["backend"] == "authlib"
    assert proof["oauth2_session_available"] is True
    assert proof["network_call_started"] is False


class pytest_raises_validation:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            raise AssertionError("expected validation error")
        return issubclass(exc_type, ValidationError)
