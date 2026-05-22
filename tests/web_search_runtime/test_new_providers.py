from __future__ import annotations

import json

from packages.web_search_runtime import (
    DDGSWebSearchAdapter,
    MultiProviderWebSearch,
    SearXNGWebSearchAdapter,
    WebSearchFreshness,
    WebSearchQuery,
    WikipediaWebSearchAdapter,
)


# ---------------------------------------------------------------------------
# WikipediaWebSearchAdapter — offline fakes for the injectable http_fetch
# ---------------------------------------------------------------------------

def _make_opensearch_fetch(titles: list[str], descriptions: list[str], urls: list[str]):
    """Return a fake http_fetch that yields a valid OpenSearch JSON payload."""
    payload = ["query-term", titles, descriptions, urls]

    def fetch(url: str) -> bytes:
        return json.dumps(payload).encode("utf-8")

    return fetch


def test_wikipedia_adapter_parses_opensearch_results() -> None:
    fetch = _make_opensearch_fetch(
        titles=["Python (programming language)", "Python snake"],
        descriptions=["General-purpose programming language.", "A genus of constricting snakes."],
        urls=["https://en.wikipedia.org/wiki/Python_(programming_language)", "https://en.wikipedia.org/wiki/Pythonidae"],
    )
    adapter = WikipediaWebSearchAdapter(http_fetch=fetch)
    query = WebSearchQuery(query="python", max_results=2, freshness=WebSearchFreshness.ANY)

    bundle = adapter.search(query)

    assert bundle.provider == "wikipedia"
    assert len(bundle.results) == 2
    assert bundle.results[0].title == "Python (programming language)"
    assert bundle.results[0].domain == "en.wikipedia.org"
    assert bundle.results[1].url == "https://en.wikipedia.org/wiki/Pythonidae"
    assert bundle.raw_payload_persisted is False
    assert bundle.evidence_refs[0].raw_content_persisted is False


def test_wikipedia_adapter_respects_max_results() -> None:
    fetch = _make_opensearch_fetch(
        titles=["A", "B", "C", "D", "E"],
        descriptions=["desc a", "desc b", "desc c", "desc d", "desc e"],
        urls=[f"https://en.wikipedia.org/wiki/{c}" for c in "ABCDE"],
    )
    adapter = WikipediaWebSearchAdapter(http_fetch=fetch)
    query = WebSearchQuery(query="test", max_results=3, freshness=WebSearchFreshness.ANY)

    bundle = adapter.search(query)

    assert len(bundle.results) == 3


def test_wikipedia_adapter_returns_empty_bundle_on_network_error() -> None:
    def failing_fetch(url: str) -> bytes:
        raise ConnectionError("network unavailable")

    adapter = WikipediaWebSearchAdapter(http_fetch=failing_fetch)
    query = WebSearchQuery(query="test", freshness=WebSearchFreshness.ANY)

    bundle = adapter.search(query)

    assert bundle.provider == "wikipedia"
    assert len(bundle.results) == 0
    assert bundle.raw_payload_persisted is False


def test_wikipedia_adapter_clamps_long_snippets() -> None:
    long_desc = "x" * 1200
    fetch = _make_opensearch_fetch(
        titles=["Long article"],
        descriptions=[long_desc],
        urls=["https://en.wikipedia.org/wiki/Long_article"],
    )
    adapter = WikipediaWebSearchAdapter(http_fetch=fetch)
    query = WebSearchQuery(query="long", freshness=WebSearchFreshness.ANY)

    bundle = adapter.search(query)

    assert len(bundle.results[0].snippet) == 800
    assert len(bundle.evidence_refs[0].snippet) == 800


def test_wikipedia_adapter_api_key_required_is_false() -> None:
    adapter = WikipediaWebSearchAdapter()
    assert adapter.api_key_required is False


# ---------------------------------------------------------------------------
# DDGSWebSearchAdapter retry/backoff
# ---------------------------------------------------------------------------

class _RateLimitThenSuccessDDGS:
    """Simulates rate-limiting on the first N calls then succeeds."""

    def __init__(self, fail_count: int = 1) -> None:
        self.call_count = 0
        self.fail_count = fail_count
        self.sleep_calls: list[float] = []

    def text(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise RuntimeError("429 Too Many Requests – rate limited")
        return [{"title": "Retry success", "href": "https://example.test/retry", "body": "Worked after retry"}]


def test_ddgs_adapter_retries_on_rate_limit_and_succeeds() -> None:
    client = _RateLimitThenSuccessDDGS(fail_count=1)
    sleep_calls: list[float] = []
    adapter = DDGSWebSearchAdapter(ddgs_client=client, max_retries=3, backoff_base_seconds=0.01, sleep_fn=sleep_calls.append)
    query = WebSearchQuery(query="test", freshness=WebSearchFreshness.ANY)

    bundle = adapter.search(query)

    assert bundle.provider == "ddgs"
    assert len(bundle.results) == 1
    assert bundle.results[0].title == "Retry success"
    assert len(sleep_calls) == 1  # one backoff sleep before the successful retry
    assert sleep_calls[0] == pytest.approx(0.01, rel=0.1)


def test_ddgs_adapter_gives_up_after_max_retries() -> None:
    client = _RateLimitThenSuccessDDGS(fail_count=10)  # always fails
    sleep_calls: list[float] = []
    adapter = DDGSWebSearchAdapter(ddgs_client=client, max_retries=2, backoff_base_seconds=0.001, sleep_fn=sleep_calls.append)
    query = WebSearchQuery(query="test", freshness=WebSearchFreshness.ANY)

    raised = False
    try:
        adapter.search(query)
    except RuntimeError:
        raised = True

    assert raised
    assert len(sleep_calls) == 2  # slept before retry 1 and retry 2


def test_ddgs_adapter_does_not_retry_non_rate_limit_errors() -> None:
    class _ImmediateFailDDGS:
        def text(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
            raise ValueError("bad query format")

    sleep_calls: list[float] = []
    adapter = DDGSWebSearchAdapter(ddgs_client=_ImmediateFailDDGS(), max_retries=3, backoff_base_seconds=0.01, sleep_fn=sleep_calls.append)
    query = WebSearchQuery(query="test", freshness=WebSearchFreshness.ANY)

    raised = False
    try:
        adapter.search(query)
    except ValueError:
        raised = True

    assert raised
    assert len(sleep_calls) == 0  # no retry for non-rate-limit errors


# ---------------------------------------------------------------------------
# MultiProviderWebSearch fallback
# ---------------------------------------------------------------------------

class _EmptyProvider:
    provider_name = "empty"

    def search(self, query: WebSearchQuery) -> "WebSearchGroundingBundle":
        from packages.web_search_runtime import WebSearchGroundingBundle
        return WebSearchGroundingBundle(query=query, provider="empty", results=(), evidence_refs=())


class _RaisingProvider:
    provider_name = "raising"

    def search(self, query: WebSearchQuery) -> "WebSearchGroundingBundle":
        raise RuntimeError("provider unavailable")


class _GoodProvider:
    provider_name = "good"

    def __init__(self, title: str = "Good result") -> None:
        self._title = title

    def search(self, query: WebSearchQuery) -> "WebSearchGroundingBundle":
        from packages.web_search_runtime import (
            WebSearchEvidenceRef,
            WebSearchGroundingBundle,
            WebSearchResult,
        )
        result = WebSearchResult(title=self._title, url="https://example.test/good", domain="example.test", snippet="Good snippet", freshness=query.freshness)
        ref = WebSearchEvidenceRef(evidence_id="web.evidence.1", source_url=result.url, domain=result.domain, title=result.title, snippet=result.snippet, freshness=result.freshness)
        return WebSearchGroundingBundle(query=query, provider="good", results=(result,), evidence_refs=(ref,))


def test_multi_provider_returns_first_non_empty_result() -> None:
    query = WebSearchQuery(query="test", freshness=WebSearchFreshness.ANY)
    multi = MultiProviderWebSearch(providers=(_EmptyProvider(), _GoodProvider(), _GoodProvider("Second")))

    bundle = multi.search(query)

    assert bundle.provider == "good"
    assert bundle.results[0].title == "Good result"


def test_multi_provider_skips_raising_providers() -> None:
    query = WebSearchQuery(query="test", freshness=WebSearchFreshness.ANY)
    multi = MultiProviderWebSearch(providers=(_RaisingProvider(), _GoodProvider()))

    bundle = multi.search(query)

    assert bundle.provider == "good"
    assert len(bundle.results) == 1


def test_multi_provider_returns_empty_bundle_when_all_fail() -> None:
    query = WebSearchQuery(query="test", freshness=WebSearchFreshness.ANY)
    multi = MultiProviderWebSearch(providers=(_RaisingProvider(), _EmptyProvider()))

    bundle = multi.search(query)

    assert len(bundle.results) == 0
    assert bundle.raw_payload_persisted is False


def test_multi_provider_returns_empty_bundle_with_no_providers() -> None:
    query = WebSearchQuery(query="test", freshness=WebSearchFreshness.ANY)
    multi = MultiProviderWebSearch(providers=())

    bundle = multi.search(query)

    assert bundle.provider == "multi"
    assert len(bundle.results) == 0


def test_multi_provider_provider_name() -> None:
    multi = MultiProviderWebSearch(providers=())
    assert multi.provider_name == "multi"


# ---------------------------------------------------------------------------
# services/core/main.py provider selection
# ---------------------------------------------------------------------------

def test_web_search_provider_from_config_wikipedia() -> None:
    from services.core.main import CoreServiceEntrypointConfig, _web_search_provider_from_config

    config = CoreServiceEntrypointConfig(web_search="wikipedia")
    provider = _web_search_provider_from_config(config)

    assert isinstance(provider, WikipediaWebSearchAdapter)
    assert provider.api_key_required is False


def test_web_search_provider_from_config_multi_no_searxng() -> None:
    from services.core.main import CoreServiceEntrypointConfig, _web_search_provider_from_config

    config = CoreServiceEntrypointConfig(web_search="multi", web_base_url=None)
    provider = _web_search_provider_from_config(config)

    assert isinstance(provider, MultiProviderWebSearch)
    assert len(provider.providers) == 2
    assert isinstance(provider.providers[0], DDGSWebSearchAdapter)
    assert isinstance(provider.providers[1], WikipediaWebSearchAdapter)


def test_web_search_provider_from_config_multi_with_searxng() -> None:
    from services.core.main import CoreServiceEntrypointConfig, _web_search_provider_from_config

    config = CoreServiceEntrypointConfig(web_search="multi", web_base_url="https://searxng.local")
    provider = _web_search_provider_from_config(config)

    assert isinstance(provider, MultiProviderWebSearch)
    assert len(provider.providers) == 3
    assert isinstance(provider.providers[2], SearXNGWebSearchAdapter)


import pytest  # noqa: E402 — imported at end to keep test functions readable above
