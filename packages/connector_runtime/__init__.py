from .models import (
    AutoFetchJobRef,
    AutoFetchPolicy,
    AutoFetchRunSummary,
    AutoFetchSchedule,
    ConnectorCategory,
    ConnectorErrorEnvelope,
    ConnectorManifest,
    ConnectorPermissionDecision,
    ConnectorRef,
    ConnectorSafeProjection,
    ConnectorScope,
    ConnectorSyncRequest,
    ConnectorSyncResult,
    OAuthConnectionRef,
    OAuthConnectionStatus,
    SourceIngestionPolicy,
    SourceLastSyncStatus,
    SourceSyncInterval,
    SourceSyncMode,
    default_connector_manifests,
)

__all__ = [
    "AutoFetchJobRef",
    "AutoFetchPolicy",
    "AutoFetchRunSummary",
    "AutoFetchSchedule",
    "ConnectorCategory",
    "ConnectorErrorEnvelope",
    "ConnectorManifest",
    "ConnectorPermissionDecision",
    "ConnectorRef",
    "ConnectorRuntime",
    "ConnectorSafeProjection",
    "ConnectorScope",
    "ConnectorSyncRequest",
    "ConnectorSyncResult",
    "ConnectorSyncRunResult",
    "OAuthConnectionRef",
    "OAuthConnectionStatus",
    "SourceIngestionPolicy",
    "SourceLastSyncStatus",
    "SourceSyncInterval",
    "SourceSyncMode",
    "default_connector_manifests",
]


def __getattr__(name: str):
    if name in {"ConnectorRuntime", "ConnectorSyncRunResult"}:
        from .runtime import ConnectorRuntime, ConnectorSyncRunResult

        return {"ConnectorRuntime": ConnectorRuntime, "ConnectorSyncRunResult": ConnectorSyncRunResult}[name]
    raise AttributeError(name)
