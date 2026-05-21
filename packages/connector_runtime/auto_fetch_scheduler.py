from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import Field

from .models import (
    AutoFetchPolicy,
    AutoFetchRunSummary,
    ConnectorRef,
    ConnectorRuntimeModel,
    SourceSyncInterval,
)


# ---------------------------------------------------------------------------
# KV persistence protocol – injected so no I/O in this module
# ---------------------------------------------------------------------------


@runtime_checkable
class KVStore(Protocol):
    """Minimal key/value store protocol; injected for testability."""

    def get(self, key: str) -> str | None:
        """Return the value stored under *key*, or ``None`` if absent."""
        ...

    def set(self, key: str, value: str) -> None:
        """Persist *value* under *key*."""
        ...


# ---------------------------------------------------------------------------
# Scheduler status enum
# ---------------------------------------------------------------------------


class SchedulerTickStatus(StrEnum):
    SYNCED = "synced"
    SKIPPED_INTERVAL = "skipped_interval"
    SKIPPED_BUDGET = "skipped_budget"
    SKIPPED_DISABLED = "skipped_disabled"
    ERROR_SWALLOWED = "error_swallowed"


# ---------------------------------------------------------------------------
# Per-connection sync state
# ---------------------------------------------------------------------------


class ConnectionSyncState(ConnectorRuntimeModel):
    """Per-(connector_id, connection_id) persistent sync state."""

    connection_id: str
    connector_id: str
    last_sync_at: datetime | None = None
    cursor: str | None = None
    daily_requests_used: int = Field(default=0, ge=0)
    daily_window_date: str | None = None  # ISO date "YYYY-MM-DD"
    dedup_hashes: tuple[str, ...] = ()
    raw_credentials_persisted: Literal[False] = False

    def with_sync(
        self,
        *,
        now: datetime,
        new_cursor: str | None,
        new_hashes: tuple[str, ...],
    ) -> "ConnectionSyncState":
        """Return a new state reflecting a completed sync at *now*."""
        today = now.date().isoformat()
        used = self.daily_requests_used + 1
        if self.daily_window_date != today:
            used = 1

        # Bound the dedup set to the most-recent 200 hashes
        merged: tuple[str, ...] = tuple(
            dict.fromkeys(self.dedup_hashes + new_hashes)
        )[-200:]

        return ConnectionSyncState(
            connection_id=self.connection_id,
            connector_id=self.connector_id,
            last_sync_at=now,
            cursor=new_cursor or self.cursor,
            daily_requests_used=used,
            daily_window_date=today,
            dedup_hashes=merged,
        )

    def budget_exhausted(self, *, daily_budget: int, now: datetime) -> bool:
        today = now.date().isoformat()
        if self.daily_window_date != today:
            return False
        return self.daily_requests_used >= daily_budget

    def interval_elapsed(self, *, interval_secs: int, now: datetime) -> bool:
        if self.last_sync_at is None:
            return True
        return (now - self.last_sync_at) >= timedelta(seconds=interval_secs)


# ---------------------------------------------------------------------------
# Per-provider sync configuration
# ---------------------------------------------------------------------------


class ProviderSyncConfig(ConnectorRuntimeModel):
    """Minimum per-provider sync settings.  DISABLED by default."""

    connector_id: str
    sync_interval_secs: int = Field(default=1200, ge=60)  # 20-minute default
    daily_request_budget: int = Field(default=50, ge=1)
    auto_fetch_enabled: bool = False  # Explicitly DISABLED by default


# ---------------------------------------------------------------------------
# Fetched page (provided by adapter; contains no raw credentials)
# ---------------------------------------------------------------------------


class FetchedPage(ConnectorRuntimeModel):
    """One page of items returned by a connector fetch client."""

    connector_ref: ConnectorRef
    connection_id: str
    # Each item is (external_id, title, markdown_body); raw account content
    # must NOT be stored here – adapters must canonicalize before wrapping.
    items: tuple[tuple[str, str, str], ...]
    next_cursor: str | None = None
    raw_payload_persisted: Literal[False] = False


# ---------------------------------------------------------------------------
# Scheduler tick result
# ---------------------------------------------------------------------------


class SchedulerTickResult(ConnectorRuntimeModel):
    connection_id: str
    connector_id: str
    status: SchedulerTickStatus
    documents_canonicalized: int = Field(default=0, ge=0)
    chunks_created: int = Field(default=0, ge=0)
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "connection_id": self.connection_id,
            "connector_id": self.connector_id,
            "status": self.status,
            "documents_canonicalized": self.documents_canonicalized,
            "chunks_created": self.chunks_created,
            "raw_payload_persisted": False,
        }


# ---------------------------------------------------------------------------
# Interval helpers (no I/O)
# ---------------------------------------------------------------------------

_INTERVAL_SECS: dict[str, int] = {
    SourceSyncInterval.MANUAL_ONLY: 0,
    SourceSyncInterval.HOURLY: 3600,
    SourceSyncInterval.DAILY: 86400,
    SourceSyncInterval.WEEKLY: 604800,
}
_DEFAULT_TICK_SECS = 1200  # 20 minutes


def effective_interval_secs(provider_min: int, interval: str | SourceSyncInterval) -> int:
    """Return effective sync interval in seconds; *provider_min* acts as floor."""
    named = _INTERVAL_SECS.get(str(interval), _DEFAULT_TICK_SECS)
    if named == 0:
        # MANUAL_ONLY → never run automatically
        return 2**31
    return max(provider_min, named)


def default_sync_config(connector_id: str) -> ProviderSyncConfig:
    """Return a disabled-by-default ``ProviderSyncConfig`` for *connector_id*."""
    return ProviderSyncConfig(connector_id=connector_id)


def make_autofetch_run_summary(
    *,
    policy: AutoFetchPolicy,
    connection_id: str,
    tick_result: SchedulerTickResult,
    now: datetime,
) -> AutoFetchRunSummary:
    """Convert a ``SchedulerTickResult`` into an ``AutoFetchRunSummary``."""
    status_map: dict[SchedulerTickStatus, str] = {
        SchedulerTickStatus.SYNCED: "completed",
        SchedulerTickStatus.SKIPPED_INTERVAL: "skipped",
        SchedulerTickStatus.SKIPPED_BUDGET: "skipped",
        SchedulerTickStatus.SKIPPED_DISABLED: "skipped",
        SchedulerTickStatus.ERROR_SWALLOWED: "failed",
    }
    return AutoFetchRunSummary(
        run_id=f"scheduler.{policy.connector_ref.connector_id}.{connection_id}",
        connector_ref=policy.connector_ref,
        started_at=now,
        completed_at=now,
        status=status_map.get(tick_result.status, "skipped"),  # type: ignore[arg-type]
        documents_seen=tick_result.documents_canonicalized,
        documents_canonicalized=tick_result.documents_canonicalized,
        chunks_created=tick_result.chunks_created,
    )
