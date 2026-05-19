
from __future__ import annotations

from enum import Enum
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel


class WebSearchFreshness(str, Enum):
    ANY = "any"
    RECENT = "recent"
    CURRENT = "current"


class WebSearchQuery(CapabilityRuntimeModel):
    query: str = Field(..., min_length=1, max_length=400)
    freshness: WebSearchFreshness = WebSearchFreshness.ANY
    max_results: int = Field(default=5, ge=1, le=10)
    raw_query_persisted: bool = False


class WebSearchResult(CapabilityRuntimeModel):
    title: str = Field(..., min_length=1, max_length=300)
    url: str = Field(..., min_length=1, max_length=1200)
    domain: str = Field(..., min_length=1, max_length=300)
    snippet: str = Field(default="", max_length=800)
    freshness: WebSearchFreshness = WebSearchFreshness.ANY
    published_at: str | None = None
    raw_result_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {"title": self.title, "url": self.url, "domain": self.domain, "snippet_present": bool(self.snippet), "freshness": self.freshness.value, "published_at": self.published_at, "raw_result_persisted": False}


class WebSearchEvidenceRef(CapabilityRuntimeModel):
    evidence_id: str = Field(..., min_length=1)
    source_url: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    snippet: str = Field(default="", max_length=800)
    freshness: WebSearchFreshness = WebSearchFreshness.ANY
    raw_content_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {"evidence_id": self.evidence_id, "source_url": self.source_url, "domain": self.domain, "title": self.title, "snippet_present": bool(self.snippet), "freshness": self.freshness.value, "raw_content_persisted": False}


class WebSearchGroundingBundle(CapabilityRuntimeModel):
    query: WebSearchQuery
    provider: str
    results: tuple[WebSearchResult, ...]
    evidence_refs: tuple[WebSearchEvidenceRef, ...]
    raw_payload_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {"query": self.query.query, "provider": self.provider, "result_count": len(self.results), "evidence_count": len(self.evidence_refs), "results": tuple(result.safe_projection() for result in self.results), "evidence_refs": tuple(ref.safe_projection() for ref in self.evidence_refs), "raw_payload_persisted": False}


class WebSearchProvider(Protocol):
    provider_name: str

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        ...


class SearXNGWebSearchAdapter(CapabilityRuntimeModel):
    provider_name: str = "searxng"
    base_url: str
    http_client: Any | None = None
    timeout_seconds: float = 10.0
    api_key_required: bool = False

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        client = self.http_client or httpx.Client()
        url = self.base_url.rstrip("/") + "/search"
        response = client.get(url, params={"q": query.query, "format": "json", "language": "en"}, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        rows = tuple(_result_from_searxng(item, query.freshness) for item in tuple(payload.get("results", ()))[: query.max_results])
        return _bundle(query, "searxng", rows)


class DDGSWebSearchAdapter(CapabilityRuntimeModel):
    provider_name: str = "ddgs"
    ddgs_client: Any | None = None

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        client = self.ddgs_client
        if client is None:
            from ddgs import DDGS

            client = DDGS()
        rows = tuple(_result_from_ddgs(item, query.freshness) for item in tuple(client.text(query.query, max_results=query.max_results)))
        return _bundle(query, "ddgs", rows)


class WebSearchProviderSelector(CapabilityRuntimeModel):
    searxng: SearXNGWebSearchAdapter | None = None
    ddgs: DDGSWebSearchAdapter | None = None

    def select_provider(self) -> WebSearchProvider:
        if self.searxng is not None:
            return self.searxng
        if self.ddgs is not None:
            return self.ddgs
        raise RuntimeError("web_search_provider_unavailable")


def _result_from_searxng(item: dict[str, Any], freshness: WebSearchFreshness) -> WebSearchResult:
    url = str(item.get("url") or item.get("href") or "")
    return WebSearchResult(title=str(item.get("title") or "Untitled result"), url=url, domain=_domain(url), snippet=str(item.get("content") or item.get("body") or ""), freshness=freshness, published_at=item.get("publishedDate"))


def _result_from_ddgs(item: dict[str, Any], freshness: WebSearchFreshness) -> WebSearchResult:
    url = str(item.get("href") or item.get("url") or "")
    return WebSearchResult(title=str(item.get("title") or "Untitled result"), url=url, domain=_domain(url), snippet=str(item.get("body") or item.get("content") or ""), freshness=freshness)


def _bundle(query: WebSearchQuery, provider: str, rows: tuple[WebSearchResult, ...]) -> WebSearchGroundingBundle:
    refs = tuple(WebSearchEvidenceRef(evidence_id=f"web.evidence.{index + 1}", source_url=row.url, domain=row.domain, title=row.title, snippet=row.snippet, freshness=row.freshness) for index, row in enumerate(rows))
    return WebSearchGroundingBundle(query=query, provider=provider, results=rows, evidence_refs=refs)


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or "unknown"
