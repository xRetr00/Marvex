
from __future__ import annotations

from packages.web_search_runtime import (
    DDGSWebSearchAdapter,
    SearXNGWebSearchAdapter,
    WebSearchFreshness,
    WebSearchProviderSelector,
    WebSearchQuery,
)


class FakeResponse:
    def json(self):
        return {
            "results": [
                {"title": "Browser Use release", "url": "https://example.test/browser-use", "content": "Current release notes", "publishedDate": "2026-05-18"}
            ]
        }

    def raise_for_status(self):
        return None


class FakeHttpClient:
    def __init__(self):
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        return FakeResponse()


class FakeDDGSClient:
    def text(self, query, max_results=5):
        assert query == "latest browser-use version"
        return [
            {"title": "DDGS result", "href": "https://example.test/ddgs", "body": "Search snippet"},
        ][:max_results]


def test_searxng_adapter_parses_json_results_without_api_key() -> None:
    client = FakeHttpClient()
    adapter = SearXNGWebSearchAdapter(base_url="https://searxng.test", http_client=client)
    query = WebSearchQuery(query="latest browser-use version", freshness=WebSearchFreshness.CURRENT)

    bundle = adapter.search(query)

    assert client.calls[0][0] == "https://searxng.test/search"
    assert client.calls[0][1]["format"] == "json"
    assert bundle.provider == "searxng"
    assert bundle.results[0].url == "https://example.test/browser-use"
    assert bundle.evidence_refs[0].domain == "example.test"
    assert bundle.raw_payload_persisted is False
    assert "Current release notes" not in bundle.safe_projection()["results"][0]


def test_ddgs_adapter_uses_real_package_boundary_with_mocked_client() -> None:
    adapter = DDGSWebSearchAdapter(ddgs_client=FakeDDGSClient())
    query = WebSearchQuery(query="latest browser-use version", freshness=WebSearchFreshness.CURRENT)

    bundle = adapter.search(query)

    assert bundle.provider == "ddgs"
    assert bundle.results[0].title == "DDGS result"
    assert bundle.evidence_refs[0].source_url == "https://example.test/ddgs"
    assert bundle.safe_projection()["provider"] == "ddgs"


def test_ddgs_adapter_clamps_long_snippets_to_safe_projection_limit() -> None:
    class LongSnippetDDGSClient:
        def text(self, query, max_results=5):
            return [
                {
                    "title": "Long DDGS result",
                    "href": "https://example.test/long-ddgs",
                    "body": "x" * 1200,
                }
            ]

    adapter = DDGSWebSearchAdapter(ddgs_client=LongSnippetDDGSClient())
    query = WebSearchQuery(query="latest browser-use version", freshness=WebSearchFreshness.CURRENT)

    bundle = adapter.search(query)

    assert len(bundle.results[0].snippet) == 800
    assert len(bundle.evidence_refs[0].snippet) == 800


def test_provider_selector_prefers_configured_searxng_then_ddgs_fallback() -> None:
    searxng = SearXNGWebSearchAdapter(base_url="https://searxng.test", http_client=FakeHttpClient())
    ddgs = DDGSWebSearchAdapter(ddgs_client=FakeDDGSClient())

    assert WebSearchProviderSelector(searxng=searxng, ddgs=ddgs).select_provider().provider_name == "searxng"
    assert WebSearchProviderSelector(searxng=None, ddgs=ddgs).select_provider().provider_name == "ddgs"
