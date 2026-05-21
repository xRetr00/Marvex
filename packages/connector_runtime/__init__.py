from .auto_fetch_scheduler import (
    ConnectionSyncState,
    FetchedPage,
    KVStore,
    ProviderSyncConfig,
    SchedulerTickResult,
    SchedulerTickStatus,
    default_sync_config,
    effective_interval_secs,
    make_autofetch_run_summary,
)
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
    "ConnectionSyncState",
    "FetchedPage",
    "KVStore",
    "OAuthConnectionRef",
    "OAuthConnectionStatus",
    "ProviderSyncConfig",
    "SchedulerTickResult",
    "SchedulerTickStatus",
    "SourceIngestionPolicy",
    "SourceLastSyncStatus",
    "SourceSyncInterval",
    "SourceSyncMode",
    "default_connector_manifests",
    "default_sync_config",
    "effective_interval_secs",
    "make_autofetch_run_summary",
]


def __getattr__(name: str):
    if name in {"ConnectorRuntime", "ConnectorSyncRunResult"}:
        from .runtime import ConnectorRuntime, ConnectorSyncRunResult

        return {"ConnectorRuntime": ConnectorRuntime, "ConnectorSyncRunResult": ConnectorSyncRunResult}[name]
    raise AttributeError(name)
