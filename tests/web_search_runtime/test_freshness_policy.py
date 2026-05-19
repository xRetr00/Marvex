from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.web_search_runtime import FreshnessPolicy, WebSearchFreshness


def test_freshness_policy_detects_implicit_library_version_and_stale_source() -> None:
    policy = FreshnessPolicy.default()
    captured = datetime.now(UTC) - timedelta(days=120)

    decision = policy.evaluate(query="is browser-use compatible with our OpenAI SDK", source_type="dependency_docs", source_timestamp=captured)

    assert decision.freshness_needed is True
    assert decision.source_is_stale is True
    assert decision.recommended_freshness == WebSearchFreshness.CURRENT
    assert decision.reason_code == "freshness.current_dependency_or_docs"


def test_freshness_policy_allows_recent_non_current_memory() -> None:
    policy = FreshnessPolicy.default()
    captured = datetime.now(UTC) - timedelta(days=1)

    decision = policy.evaluate(query="what did I decide about Marvex architecture", source_type="memory", source_timestamp=captured)

    assert decision.source_is_stale is False
    assert decision.freshness_needed is False
