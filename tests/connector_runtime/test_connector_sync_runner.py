from datetime import UTC, datetime

from packages.capability_runtime import AutonomyMode, AutonomyPolicy
from packages.connector_runtime import ConnectorCategory, ConnectorRef, ConnectorRuntime, ConnectorSyncRequest, ConnectorPermissionDecision, SourceSyncMode


def test_mock_connector_sync_canonicalizes_documents_into_memory_tree_chunks_with_audit() -> None:
    connector_ref = ConnectorRef(connector_id="mock-local", category=ConnectorCategory.GENERIC_OAUTH)
    runtime = ConnectorRuntime.mock(
        connector_ref=connector_ref,
        documents=(("doc-1", "Mock Connector Note", "Connector sync evidence enters memory tree runtime."),),
        autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX),
    )
    request = ConnectorSyncRequest(
        request_id="sync-mock-1",
        connector_ref=connector_ref,
        sync_mode=SourceSyncMode.ON_DEMAND,
        permission_decision=ConnectorPermissionDecision.APPROVED,
        requested_at=datetime(2026, 5, 19, tzinfo=UTC),
    )

    result = runtime.sync(request)

    assert result.sync_result.status == "completed"
    assert result.sync_result.documents_seen == 1
    assert result.documents[0].metadata.title == "Mock Connector Note"
    assert result.chunks[0].markdown == "Connector sync evidence enters memory tree runtime."
    assert result.memory_tree.memory_tree_search("sync evidence").results
    assert result.audit_record.decision.value == "allow"
    assert result.safe_projection()["raw_payload_persisted"] is False


def test_scheduled_autofetch_uses_policy_and_records_failures_without_background_sync() -> None:
    connector_ref = ConnectorRef(connector_id="mock-local", category=ConnectorCategory.GENERIC_OAUTH)
    runtime = ConnectorRuntime.mock(connector_ref=connector_ref, documents=(), autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.ASK_BEFORE_RISKY))

    run = runtime.run_autofetch(now=datetime(2026, 5, 19, tzinfo=UTC))

    assert run.status == "skipped"
    assert run.documents_seen == 0
    assert runtime.untracked_background_sync_started is False
    assert run.safe_projection()["raw_payload_persisted"] is False
