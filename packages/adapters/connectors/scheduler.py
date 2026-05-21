from __future__ import annotations

"""
AutoFetchScheduler implementation.

Lives in the adapters layer (not connector_runtime) so it may import json,
logging, and other stdlib I/O without violating the connector_runtime import
boundary enforced by check_memory_tree_connector_boundaries.py.

DISABLED by default; enablement requires an explicit ProviderSyncConfig with
auto_fetch_enabled=True AND a matching AutoFetchPolicy with
control_state="enabled".

Errors from fetch/ingest are caught-and-swallowed; a bad connection never
crashes the scheduler loop.

Sync state (last-sync timestamp, cursor, dedup hashes, daily budget) is
persisted via the injected KVStore so restarts are harmless.
"""

import json
import logging
from datetime import datetime
from typing import Callable, Sequence

from packages.connector_runtime.auto_fetch_scheduler import (
    ConnectionSyncState,
    FetchedPage,
    KVStore,
    ProviderSyncConfig,
    SchedulerTickResult,
    SchedulerTickStatus,
    effective_interval_secs,
    make_autofetch_run_summary,
)
from packages.connector_runtime.models import (
    AutoFetchPolicy,
    AutoFetchRunSummary,
    ConnectorRef,
)
from packages.connector_runtime.runtime import (
    CanonicalMemoryDocument,
    CanonicalSourceMetadata,
    MemoryChunk,
    canonicalize_source_document,
    chunk_document,
)

_log = logging.getLogger(__name__)

_KV_PREFIX = "autofetch.state."
_STATE_VERSION = "v1"

FetchClient = Callable[
    [ConnectorRef, str | None],  # (connector_ref, cursor) → FetchedPage
    FetchedPage,
]

IngestCallback = Callable[
    [tuple[CanonicalMemoryDocument, ...], tuple[MemoryChunk, ...]],
    None,
]


# ---------------------------------------------------------------------------
# KV serialization helpers
# ---------------------------------------------------------------------------


def _state_key(connector_id: str, connection_id: str) -> str:
    return f"{_KV_PREFIX}{connector_id}.{connection_id}"


def _load_state(
    kv: KVStore,
    connector_ref: ConnectorRef,
    connection_id: str,
) -> ConnectionSyncState:
    key = _state_key(connector_ref.connector_id, connection_id)
    raw = kv.get(key)
    if raw is None:
        return ConnectionSyncState(
            connection_id=connection_id, connector_id=connector_ref.connector_id
        )
    try:
        data: dict = json.loads(raw)
        data.pop("version", None)
        if data.get("last_sync_at"):
            data["last_sync_at"] = datetime.fromisoformat(data["last_sync_at"])
        if isinstance(data.get("dedup_hashes"), list):
            data["dedup_hashes"] = tuple(data["dedup_hashes"])
        return ConnectionSyncState(**data)
    except Exception:  # noqa: BLE001 – corrupt entry; start fresh
        _log.debug("autofetch: corrupt KV entry for %s/%s – resetting", connector_ref.connector_id, connection_id)
        return ConnectionSyncState(
            connection_id=connection_id, connector_id=connector_ref.connector_id
        )


def _save_state(kv: KVStore, state: ConnectionSyncState) -> None:
    try:
        data = state.model_dump(mode="json")
        data["version"] = _STATE_VERSION
        if state.last_sync_at:
            data["last_sync_at"] = state.last_sync_at.isoformat()
        data["dedup_hashes"] = list(state.dedup_hashes)
        kv.set(_state_key(state.connector_id, state.connection_id), json.dumps(data))
    except Exception:  # noqa: BLE001 – KV write errors must never crash the scheduler
        _log.debug("autofetch: KV write failed for %s/%s", state.connector_id, state.connection_id)


# ---------------------------------------------------------------------------
# Canonicalization pipeline
# ---------------------------------------------------------------------------


def _canonicalize_page(
    page: FetchedPage,
    *,
    now: datetime,
    known_hashes: frozenset[str],
) -> tuple[tuple[CanonicalMemoryDocument, ...], tuple[MemoryChunk, ...], tuple[str, ...]]:
    """
    Convert a FetchedPage into canonical documents and memory chunks.

    Items whose external_id is already in *known_hashes* are skipped (dedup).
    Returns (documents, chunks, new_dedup_hashes).
    No raw content or credentials are persisted.
    """
    docs: list[CanonicalMemoryDocument] = []
    chunks_all: list[MemoryChunk] = []
    new_hashes: list[str] = []

    for external_id, title, body in page.items:
        if external_id in known_hashes:
            continue
        metadata = CanonicalSourceMetadata(
            source_id=f"source.{page.connector_ref.connector_id}",
            external_id=external_id,
            uri=f"connector://{page.connector_ref.connector_id}/{external_id}",
            title=title,
            connector_ref=page.connector_ref,
            captured_at=now,
        )
        doc = canonicalize_source_document(metadata=metadata, markdown_body=body, ingested_at=now)
        page_chunks = chunk_document(doc)
        docs.append(doc)
        chunks_all.extend(page_chunks)
        new_hashes.append(external_id)

    return tuple(docs), tuple(chunks_all), tuple(new_hashes)


# ---------------------------------------------------------------------------
# AutoFetchScheduler
# ---------------------------------------------------------------------------


class AutoFetchScheduler:
    """
    Periodic auto-fetch scheduler with per-connection state.

    DISABLED by default.  Enablement requires:
      - ProviderSyncConfig(auto_fetch_enabled=True)
      - AutoFetchPolicy(control_state="enabled", connector_enabled=True, source_enabled=True)

    Errors from fetch/ingest are caught-and-swallowed so a bad connection never
    crashes the scheduler loop.  Sync state is persisted via KVStore so restarts
    are harmless (cursor, dedup, budget, last-sync timestamp all resume).
    """

    def __init__(
        self,
        *,
        kv: KVStore,
        fetch_client: FetchClient,
        provider_configs: Sequence[ProviderSyncConfig] | None = None,
        ingest_callback: IngestCallback | None = None,
    ) -> None:
        self._kv = kv
        self._fetch_client = fetch_client
        self._configs: dict[str, ProviderSyncConfig] = {
            cfg.connector_id: cfg for cfg in (provider_configs or ())
        }
        self._ingest_callback = ingest_callback

    def register_config(self, config: ProviderSyncConfig) -> None:
        self._configs[config.connector_id] = config

    def tick(
        self,
        *,
        policy: AutoFetchPolicy,
        connection_id: str,
        now: datetime,
    ) -> SchedulerTickResult:
        """
        Evaluate and optionally perform one sync tick for a connection.

        Always returns a SchedulerTickResult; errors are swallowed.
        """
        connector_ref = policy.connector_ref
        cid = connector_ref.connector_id

        # 1. Guard: disabled by default
        cfg = self._configs.get(cid)
        policy_active = (
            policy.control_state == "enabled"
            and policy.connector_enabled
            and policy.source_enabled
        )
        if cfg is None or not cfg.auto_fetch_enabled or not policy_active:
            return SchedulerTickResult(
                connection_id=connection_id,
                connector_id=cid,
                status=SchedulerTickStatus.SKIPPED_DISABLED,
            )

        # 2. Load persisted state
        state = _load_state(self._kv, connector_ref, connection_id)

        # 3. Budget check
        if state.budget_exhausted(daily_budget=cfg.daily_request_budget, now=now):
            return SchedulerTickResult(
                connection_id=connection_id,
                connector_id=cid,
                status=SchedulerTickStatus.SKIPPED_BUDGET,
            )

        # 4. Interval check
        interval_secs = effective_interval_secs(cfg.sync_interval_secs, policy.schedule.interval)
        if not state.interval_elapsed(interval_secs=interval_secs, now=now):
            return SchedulerTickResult(
                connection_id=connection_id,
                connector_id=cid,
                status=SchedulerTickStatus.SKIPPED_INTERVAL,
            )

        # 5. Fetch and canonicalize (errors swallowed)
        try:
            return self._do_sync(
                connector_ref=connector_ref,
                connection_id=connection_id,
                state=state,
                cfg=cfg,
                now=now,
            )
        except Exception:  # noqa: BLE001 – errors swallowed; never crash scheduler
            _log.debug("autofetch: sync error for %s/%s (swallowed)", cid, connection_id)
            return SchedulerTickResult(
                connection_id=connection_id,
                connector_id=cid,
                status=SchedulerTickStatus.ERROR_SWALLOWED,
            )

    def _do_sync(
        self,
        *,
        connector_ref: ConnectorRef,
        connection_id: str,
        state: ConnectionSyncState,
        cfg: ProviderSyncConfig,
        now: datetime,
    ) -> SchedulerTickResult:
        page = self._fetch_client(connector_ref, state.cursor)
        known = frozenset(state.dedup_hashes)
        docs, chunks, new_hashes = _canonicalize_page(page, now=now, known_hashes=known)

        new_state = state.with_sync(
            now=now,
            new_cursor=page.next_cursor,
            new_hashes=new_hashes,
        )
        _save_state(self._kv, new_state)

        if self._ingest_callback is not None and docs:
            try:
                self._ingest_callback(docs, chunks)
            except Exception:  # noqa: BLE001 – ingest errors swallowed
                _log.debug("autofetch: ingest callback error for %s/%s (swallowed)", connector_ref.connector_id, connection_id)

        return SchedulerTickResult(
            connection_id=connection_id,
            connector_id=connector_ref.connector_id,
            status=SchedulerTickStatus.SYNCED,
            documents_canonicalized=len(docs),
            chunks_created=len(chunks),
        )

    def run_autofetch_summary(
        self,
        *,
        policy: AutoFetchPolicy,
        connection_id: str,
        now: datetime,
    ) -> AutoFetchRunSummary:
        """Convenience wrapper returning an AutoFetchRunSummary."""
        result = self.tick(policy=policy, connection_id=connection_id, now=now)
        return make_autofetch_run_summary(
            policy=policy, connection_id=connection_id, tick_result=result, now=now
        )
