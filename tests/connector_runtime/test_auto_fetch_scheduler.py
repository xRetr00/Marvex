from __future__ import annotations

"""
Tests for AutoFetchScheduler: interval/budget/dedup/cursor, error-swallowing,
KV restart-resume, fake connector page → canonicalize → derived-safe Memory
Tree ingest, default policy DISABLED, no raw content/credentials/tokens.
"""

from datetime import UTC, datetime, timedelta

from packages.connector_runtime.auto_fetch_scheduler import (
    ConnectionSyncState,
    FetchedPage,
    KVStore,
    ProviderSyncConfig,
    SchedulerTickStatus,
    default_sync_config,
    effective_interval_secs,
)
from packages.connector_runtime.models import (
    AutoFetchPolicy,
    AutoFetchSchedule,
    ConnectorCategory,
    ConnectorRef,
    SourceSyncInterval,
)
from packages.adapters.connectors.scheduler import AutoFetchScheduler, _canonicalize_page


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class InMemoryKV:
    """Simple in-memory KVStore for tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str) -> None:
        self._store[key] = value

    def snapshot(self) -> dict[str, str]:
        return dict(self._store)


def _enabled_policy(connector_ref: ConnectorRef) -> AutoFetchPolicy:
    return AutoFetchPolicy(
        connector_ref=connector_ref,
        control_state="enabled",
        connector_enabled=True,
        source_enabled=True,
        schedule=AutoFetchSchedule(interval=SourceSyncInterval.HOURLY),
    )


def _disabled_policy(connector_ref: ConnectorRef) -> AutoFetchPolicy:
    return AutoFetchPolicy.default_for_connector(connector_ref)


def _connector_ref() -> ConnectorRef:
    return ConnectorRef(connector_id="github-connector", category=ConnectorCategory.GITHUB)


def _make_fake_fetch(items: list[tuple[str, str, str]], next_cursor: str | None = None):
    def _fetch(connector_ref: ConnectorRef, cursor: str | None) -> FetchedPage:
        return FetchedPage(
            connector_ref=connector_ref,
            connection_id=connector_ref.connector_id,
            items=tuple(items),
            next_cursor=next_cursor,
        )

    return _fetch


# ---------------------------------------------------------------------------
# Default policy is DISABLED
# ---------------------------------------------------------------------------


def test_default_provider_sync_config_is_disabled() -> None:
    cfg = default_sync_config("github-connector")
    assert cfg.auto_fetch_enabled is False


def test_scheduler_skips_when_config_missing() -> None:
    kv = InMemoryKV()
    scheduler = AutoFetchScheduler(kv=kv, fetch_client=_make_fake_fetch([]))
    policy = _enabled_policy(_connector_ref())
    result = scheduler.tick(policy=policy, connection_id="conn-1", now=datetime(2026, 5, 20, tzinfo=UTC))
    assert result.status == SchedulerTickStatus.SKIPPED_DISABLED


def test_scheduler_skips_when_auto_fetch_disabled_in_config() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(connector_id="github-connector", auto_fetch_enabled=False)
    scheduler = AutoFetchScheduler(kv=kv, fetch_client=_make_fake_fetch([]), provider_configs=[cfg])
    policy = _enabled_policy(_connector_ref())
    result = scheduler.tick(policy=policy, connection_id="conn-1", now=datetime(2026, 5, 20, tzinfo=UTC))
    assert result.status == SchedulerTickStatus.SKIPPED_DISABLED


def test_scheduler_skips_when_policy_is_disabled() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(connector_id="github-connector", auto_fetch_enabled=True)
    scheduler = AutoFetchScheduler(kv=kv, fetch_client=_make_fake_fetch([]), provider_configs=[cfg])
    policy = _disabled_policy(_connector_ref())
    result = scheduler.tick(policy=policy, connection_id="conn-1", now=datetime(2026, 5, 20, tzinfo=UTC))
    assert result.status == SchedulerTickStatus.SKIPPED_DISABLED


# ---------------------------------------------------------------------------
# Interval enforcement
# ---------------------------------------------------------------------------


def test_scheduler_honors_sync_interval() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(
        connector_id="github-connector", auto_fetch_enabled=True, sync_interval_secs=3600
    )
    fetch_called = []

    def _fetch(connector_ref, cursor):
        fetch_called.append(cursor)
        return FetchedPage(
            connector_ref=connector_ref,
            connection_id=connector_ref.connector_id,
            items=(("ext-1", "Issue 1", "Some safe body"),),
        )

    scheduler = AutoFetchScheduler(kv=kv, fetch_client=_fetch, provider_configs=[cfg])
    policy = _enabled_policy(_connector_ref())
    now = datetime(2026, 5, 20, 10, 0, 0, tzinfo=UTC)

    # First tick: no prior sync → should sync
    result1 = scheduler.tick(policy=policy, connection_id="conn-1", now=now)
    assert result1.status == SchedulerTickStatus.SYNCED
    assert len(fetch_called) == 1

    # Second tick immediately: interval not elapsed → skip
    result2 = scheduler.tick(policy=policy, connection_id="conn-1", now=now + timedelta(minutes=5))
    assert result2.status == SchedulerTickStatus.SKIPPED_INTERVAL
    assert len(fetch_called) == 1

    # Third tick after interval: should sync again
    result3 = scheduler.tick(policy=policy, connection_id="conn-1", now=now + timedelta(hours=2))
    assert result3.status == SchedulerTickStatus.SYNCED
    assert len(fetch_called) == 2


# ---------------------------------------------------------------------------
# Daily budget enforcement
# ---------------------------------------------------------------------------


def test_scheduler_honors_daily_budget() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(
        connector_id="github-connector",
        auto_fetch_enabled=True,
        sync_interval_secs=60,
        daily_request_budget=2,
    )
    scheduler = AutoFetchScheduler(
        kv=kv, fetch_client=_make_fake_fetch([("ext-1", "T", "B")]), provider_configs=[cfg]
    )
    policy = _enabled_policy(_connector_ref())
    base = datetime(2026, 5, 20, 10, 0, 0, tzinfo=UTC)

    r1 = scheduler.tick(policy=policy, connection_id="conn-1", now=base)
    assert r1.status == SchedulerTickStatus.SYNCED

    # Advance past the HOURLY effective interval (3600s)
    r2 = scheduler.tick(policy=policy, connection_id="conn-1", now=base + timedelta(hours=2))
    assert r2.status == SchedulerTickStatus.SYNCED

    # Budget exhausted for the day; even after interval has elapsed again
    r3 = scheduler.tick(policy=policy, connection_id="conn-1", now=base + timedelta(hours=4))
    assert r3.status == SchedulerTickStatus.SKIPPED_BUDGET

    # Next day: budget resets (and interval has elapsed too)
    r4 = scheduler.tick(
        policy=policy, connection_id="conn-1", now=base + timedelta(days=1, hours=1)
    )
    assert r4.status == SchedulerTickStatus.SYNCED


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_scheduler_deduplicates_items() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(
        connector_id="github-connector", auto_fetch_enabled=True, sync_interval_secs=60
    )
    items = [("ext-dup", "Dupe Item", "Already seen content")]
    scheduler = AutoFetchScheduler(
        kv=kv, fetch_client=_make_fake_fetch(items), provider_configs=[cfg]
    )
    policy = _enabled_policy(_connector_ref())
    base = datetime(2026, 5, 20, 10, 0, 0, tzinfo=UTC)

    r1 = scheduler.tick(policy=policy, connection_id="conn-1", now=base)
    assert r1.documents_canonicalized == 1

    # Second tick after HOURLY interval: same item → deduped → 0 new docs
    r2 = scheduler.tick(policy=policy, connection_id="conn-1", now=base + timedelta(hours=2))
    assert r2.documents_canonicalized == 0
    assert r2.status == SchedulerTickStatus.SYNCED


# ---------------------------------------------------------------------------
# Cursor advancement
# ---------------------------------------------------------------------------


def test_scheduler_advances_cursor() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(
        connector_id="github-connector", auto_fetch_enabled=True, sync_interval_secs=60
    )
    cursors_seen = []

    def _fetch(connector_ref, cursor):
        cursors_seen.append(cursor)
        return FetchedPage(
            connector_ref=connector_ref,
            connection_id=connector_ref.connector_id,
            items=(("ext-" + (cursor or "0"), "Title", "Body"),),
            next_cursor="page-2" if cursor is None else None,
        )

    scheduler = AutoFetchScheduler(kv=kv, fetch_client=_fetch, provider_configs=[cfg])
    policy = _enabled_policy(_connector_ref())
    base = datetime(2026, 5, 20, 10, 0, 0, tzinfo=UTC)

    scheduler.tick(policy=policy, connection_id="conn-1", now=base)
    assert cursors_seen[-1] is None  # First tick: no cursor

    # Advance past HOURLY effective interval before second tick
    scheduler.tick(policy=policy, connection_id="conn-1", now=base + timedelta(hours=2))
    assert cursors_seen[-1] == "page-2"  # Second tick: resumed from cursor


# ---------------------------------------------------------------------------
# KV persistence / restart resume
# ---------------------------------------------------------------------------


def test_scheduler_resumes_from_kv_after_restart() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(
        connector_id="github-connector", auto_fetch_enabled=True, sync_interval_secs=3600
    )
    policy = _enabled_policy(_connector_ref())
    base = datetime(2026, 5, 20, 10, 0, 0, tzinfo=UTC)

    # First scheduler instance syncs
    s1 = AutoFetchScheduler(
        kv=kv, fetch_client=_make_fake_fetch([("e1", "T1", "B1")]), provider_configs=[cfg]
    )
    r1 = s1.tick(policy=policy, connection_id="conn-1", now=base)
    assert r1.status == SchedulerTickStatus.SYNCED

    # Simulate restart: new scheduler, same KV
    s2 = AutoFetchScheduler(
        kv=kv, fetch_client=_make_fake_fetch([("e1", "T1", "B1")]), provider_configs=[cfg]
    )
    # Interval has not elapsed → should skip (state was persisted)
    r2 = s2.tick(policy=policy, connection_id="conn-1", now=base + timedelta(minutes=30))
    assert r2.status == SchedulerTickStatus.SKIPPED_INTERVAL


# ---------------------------------------------------------------------------
# Error swallowing
# ---------------------------------------------------------------------------


def test_scheduler_swallows_fetch_errors() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(connector_id="github-connector", auto_fetch_enabled=True)

    def _bad_fetch(connector_ref, cursor):
        raise RuntimeError("simulated network failure")

    scheduler = AutoFetchScheduler(kv=kv, fetch_client=_bad_fetch, provider_configs=[cfg])
    policy = _enabled_policy(_connector_ref())
    result = scheduler.tick(
        policy=policy, connection_id="conn-1", now=datetime(2026, 5, 20, tzinfo=UTC)
    )
    # Error must be swallowed; never re-raised
    assert result.status == SchedulerTickStatus.ERROR_SWALLOWED


def test_scheduler_swallows_ingest_callback_errors() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(connector_id="github-connector", auto_fetch_enabled=True)

    def _bad_ingest(docs, chunks):
        raise ValueError("ingest kaboom")

    scheduler = AutoFetchScheduler(
        kv=kv,
        fetch_client=_make_fake_fetch([("ext-1", "Title", "Body")]),
        provider_configs=[cfg],
        ingest_callback=_bad_ingest,
    )
    policy = _enabled_policy(_connector_ref())
    result = scheduler.tick(
        policy=policy, connection_id="conn-1", now=datetime(2026, 5, 20, tzinfo=UTC)
    )
    # Ingest error must be swallowed
    assert result.status == SchedulerTickStatus.SYNCED


# ---------------------------------------------------------------------------
# Canonicalize → derived-safe Memory Tree ingest
# ---------------------------------------------------------------------------


def test_canonicalize_page_produces_derived_safe_chunks() -> None:
    connector_ref = _connector_ref()
    now = datetime(2026, 5, 20, 10, 0, 0, tzinfo=UTC)
    page = FetchedPage(
        connector_ref=connector_ref,
        connection_id=connector_ref.connector_id,
        items=(
            ("ext-abc", "Safe Issue Title", "Connector auto-fetch evidence for memory tree."),
            ("ext-def", "Another Issue", "More derived content here."),
        ),
    )

    docs, chunks, new_hashes = _canonicalize_page(page, now=now, known_hashes=frozenset())

    assert len(docs) == 2
    assert len(chunks) == 2
    assert len(new_hashes) == 2

    for doc in docs:
        assert doc.raw_content_persisted is False
        assert doc.metadata.connector_ref.connector_id == "github-connector"

    for chunk in chunks:
        assert chunk.raw_content_persisted is False
        # No secret-like terms in chunk content
        low = chunk.markdown.lower()
        for term in ("token", "bearer", "secret", "password", "authorization"):
            assert term not in low, f"secret term '{term}' found in chunk"


def test_canonicalize_page_deduplicates_known_hashes() -> None:
    connector_ref = _connector_ref()
    now = datetime(2026, 5, 20, tzinfo=UTC)
    page = FetchedPage(
        connector_ref=connector_ref,
        connection_id=connector_ref.connector_id,
        items=(
            ("ext-known", "Known", "Already ingested."),
            ("ext-new", "New", "Fresh content."),
        ),
    )

    docs, chunks, new_hashes = _canonicalize_page(
        page, now=now, known_hashes=frozenset(["ext-known"])
    )

    assert len(docs) == 1
    assert docs[0].metadata.external_id == "ext-new"
    assert "ext-new" in new_hashes
    assert "ext-known" not in new_hashes


# ---------------------------------------------------------------------------
# Safe projection – no raw content / credentials / tokens
# ---------------------------------------------------------------------------


def test_scheduler_tick_result_safe_projection_has_no_raw_content() -> None:
    kv = InMemoryKV()
    cfg = ProviderSyncConfig(connector_id="github-connector", auto_fetch_enabled=True)
    scheduler = AutoFetchScheduler(
        kv=kv,
        fetch_client=_make_fake_fetch([("ext-1", "T", "Safe body only")]),
        provider_configs=[cfg],
    )
    policy = _enabled_policy(_connector_ref())
    result = scheduler.tick(
        policy=policy, connection_id="conn-1", now=datetime(2026, 5, 20, tzinfo=UTC)
    )
    projection = result.safe_projection()
    serialized = repr(projection).lower()

    assert projection["raw_payload_persisted"] is False
    for term in ("token", "bearer", "secret", "password", "authorization", "api_key"):
        assert term not in serialized, f"secret term '{term}' found in projection"


# ---------------------------------------------------------------------------
# Effective interval helpers
# ---------------------------------------------------------------------------


def test_effective_interval_secs_manual_only_returns_large_value() -> None:
    secs = effective_interval_secs(1200, SourceSyncInterval.MANUAL_ONLY)
    assert secs > 86400 * 365  # Effectively "never"


def test_effective_interval_secs_provider_min_is_floor() -> None:
    # Provider min 7200 > hourly 3600 → result should be 7200
    secs = effective_interval_secs(7200, SourceSyncInterval.HOURLY)
    assert secs == 7200


def test_effective_interval_secs_hourly_default() -> None:
    secs = effective_interval_secs(1200, SourceSyncInterval.HOURLY)
    assert secs == 3600


# ---------------------------------------------------------------------------
# ConnectionSyncState immutability
# ---------------------------------------------------------------------------


def test_connection_sync_state_with_sync_is_immutable() -> None:
    state = ConnectionSyncState(connection_id="c1", connector_id="github-connector")
    now = datetime(2026, 5, 20, tzinfo=UTC)
    new_state = state.with_sync(now=now, new_cursor="page-2", new_hashes=("h1",))
    assert state.last_sync_at is None  # original unchanged
    assert new_state.last_sync_at == now
    assert new_state.cursor == "page-2"
    assert "h1" in new_state.dedup_hashes
