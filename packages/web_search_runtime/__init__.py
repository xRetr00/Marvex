
# file size justification: multi-provider web search runtime (Wikipedia, DDGS retry,
# multi-fallback, SearXNG) plus freshness/grounding models live in this single
# governed module per the web-search boundary contract.
from __future__ import annotations

import json
import ipaddress
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Protocol
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


class WebFetchResult(CapabilityRuntimeModel):
    url: str = Field(..., min_length=1, max_length=1200)
    final_url: str = Field(..., min_length=1, max_length=1200)
    domain: str = Field(..., min_length=1, max_length=300)
    title: str = Field(default="", max_length=300)
    text_preview: str = Field(default="", max_length=8000)
    text_character_count: int = Field(default=0, ge=0)
    status_code: int | None = None
    content_type: str | None = None
    raw_html_persisted: bool = False
    raw_page_text_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "domain": self.domain,
            "title": self.title,
            "text_preview": self.text_preview,
            "text_character_count": self.text_character_count,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "raw_html_persisted": False,
            "raw_page_text_persisted": False,
        }


class WebFetchProvider(Protocol):
    def fetch(self, url: str, *, max_chars: int) -> WebFetchResult:
        ...


class TrafilaturaWebFetchAdapter(CapabilityRuntimeModel):
    timeout_seconds: float = 10.0
    user_agent: str = "Marvex-Assistant-OS/1.0"
    fetch_html: Any | None = None
    extract_text: Any | None = None

    def fetch(self, url: str, *, max_chars: int = 4000) -> WebFetchResult:
        cleaned = _validate_fetch_url(url)
        html = self._fetch_html(cleaned)
        extracted = self._extract_text(html)
        text = _bounded_text(extracted or "", max(max_chars, 1))
        return WebFetchResult(
            url=cleaned,
            final_url=cleaned,
            domain=_domain(cleaned),
            title=_html_title(html),
            text_preview=text,
            text_character_count=len(extracted or ""),
        )

    def _fetch_html(self, url: str) -> str:
        if self.fetch_html is not None:
            return str(self.fetch_html(url))
        from trafilatura.downloads import fetch_url

        html = fetch_url(url, timeout=self.timeout_seconds)
        return html or ""

    def _extract_text(self, html: str) -> str:
        if self.extract_text is not None:
            return str(self.extract_text(html))
        import trafilatura

        extracted = trafilatura.extract(
            html,
            output_format="txt",
            include_comments=False,
            include_tables=True,
        )
        return extracted or ""


# ---------------------------------------------------------------------------
# SearXNG adapter (no API key required; self-hosted)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# DDGS adapter with bounded retry/backoff for rate-limit robustness
# ---------------------------------------------------------------------------

_DDGS_MAX_RETRIES: int = 3
_DDGS_BACKOFF_BASE_SECONDS: float = 1.0


class DDGSWebSearchAdapter(CapabilityRuntimeModel):
    provider_name: str = "ddgs"
    ddgs_client: Any | None = None
    max_retries: int = _DDGS_MAX_RETRIES
    backoff_base_seconds: float = _DDGS_BACKOFF_BASE_SECONDS
    # Injectable sleep callable for testability (real runtime uses time.sleep)
    sleep_fn: Any | None = None

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        client = self.ddgs_client
        if client is None:
            from ddgs import DDGS
            client = DDGS()
        sleep_fn: Callable[[float], None] = self.sleep_fn or time.sleep
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                rows = tuple(
                    _result_from_ddgs(item, query.freshness)
                    for item in tuple(client.text(query.query, max_results=query.max_results))
                )
                return _bundle(query, "ddgs", rows)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                exc_str = str(exc).lower()
                is_rate_limit = (
                    "429" in exc_str
                    or "rate" in exc_str
                    or "ratelimit" in exc_str
                    or "too many" in exc_str
                    or "503" in exc_str
                )
                if not is_rate_limit or attempt >= self.max_retries:
                    break
                wait = self.backoff_base_seconds * (2 ** attempt)
                sleep_fn(wait)
        if last_exc is not None:
            raise last_exc
        return _bundle(query, "ddgs", ())


# ---------------------------------------------------------------------------
# Wikipedia adapter — free, no API key, stdlib urllib only
# ---------------------------------------------------------------------------

_WIKIPEDIA_API_BASE: str = "https://en.wikipedia.org/w/api.php"
_WIKIPEDIA_ARTICLE_BASE: str = "https://en.wikipedia.org/wiki/"
_WIKIPEDIA_DOMAIN: str = "en.wikipedia.org"
_WIKIPEDIA_USER_AGENT: str = "Marvex-Assistant-OS/1.0 (open-source; no-api-key; stdlib urllib)"


def _wikipedia_fetch(url: str, *, http_fetch: Callable[[str], bytes] | None) -> bytes:
    """Fetch URL bytes via injectable HTTP callable (for offline testing) or urllib."""
    if http_fetch is not None:
        return http_fetch(url)
    req = urllib.request.Request(url, headers={"User-Agent": _WIKIPEDIA_USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — stdlib, not shell
        return resp.read()


class WikipediaWebSearchAdapter(CapabilityRuntimeModel):
    """Free, open-content Wikipedia search via the MediaWiki OpenSearch API.

    Uses Python stdlib ``urllib`` only — no new dependency.
    Bounded snippets only; no raw HTML or full article text is persisted.
    api_key_required is always False (Wikipedia is openly accessible).
    """

    provider_name: str = "wikipedia"
    api_base: str = _WIKIPEDIA_API_BASE
    article_base: str = _WIKIPEDIA_ARTICLE_BASE
    api_key_required: bool = False
    # Injectable HTTP fetch callable for offline tests (signature: (url: str) -> bytes)
    http_fetch: Any | None = None

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        opensearch_params = urllib.parse.urlencode({
            "action": "opensearch",
            "search": query.query,
            "limit": query.max_results,
            "namespace": "0",
            "format": "json",
        })
        opensearch_url = f"{self.api_base}?{opensearch_params}"
        try:
            raw = _wikipedia_fetch(opensearch_url, http_fetch=self.http_fetch)
            opensearch_payload: list[Any] = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return _bundle(query, "wikipedia", ())

        # OpenSearch returns [query, [titles], [descriptions], [urls]]
        if not isinstance(opensearch_payload, list) or len(opensearch_payload) < 4:
            return _bundle(query, "wikipedia", ())

        titles: list[Any] = opensearch_payload[1]
        descriptions: list[Any] = opensearch_payload[2]
        article_urls: list[Any] = opensearch_payload[3]

        rows: list[WebSearchResult] = []
        for title_raw, desc_raw, url_raw in list(zip(titles, descriptions, article_urls))[: query.max_results]:
            title = _bounded_text(title_raw, 300)
            if not title:
                continue
            rows.append(WebSearchResult(
                title=title,
                url=_bounded_text(url_raw, 1200),
                domain=_WIKIPEDIA_DOMAIN,
                snippet=_bounded_text(desc_raw, 800),
                freshness=query.freshness,
            ))

        return _bundle(query, "wikipedia", tuple(rows))


# ---------------------------------------------------------------------------
# Multi-provider fallback: tries providers in order, returns first non-empty
# ---------------------------------------------------------------------------

class MultiProviderWebSearch(CapabilityRuntimeModel):
    """Tries an ordered list of free/open-source providers; returns first non-empty bundle.

    Falls back to the next provider when one raises or returns zero results.
    All configured providers must be free and require no API key.
    """

    provider_name: str = "multi"
    providers: tuple[Any, ...] = ()

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        last_bundle: WebSearchGroundingBundle | None = None
        for provider in self.providers:
            try:
                bundle = provider.search(query)
                if bundle.results:
                    return bundle
                last_bundle = bundle
            except Exception:  # noqa: BLE001
                continue
        # All providers empty or failed — return last empty bundle or empty multi bundle
        if last_bundle is not None:
            return last_bundle
        return _bundle(query, "multi", ())


# ---------------------------------------------------------------------------
# Provider selector (legacy; kept for backward compat)
# ---------------------------------------------------------------------------

class WebSearchProviderSelector(CapabilityRuntimeModel):
    searxng: SearXNGWebSearchAdapter | None = None
    ddgs: DDGSWebSearchAdapter | None = None

    def select_provider(self) -> WebSearchProvider:
        if self.searxng is not None:
            return self.searxng
        if self.ddgs is not None:
            return self.ddgs
        raise RuntimeError("web_search_provider_unavailable")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _result_from_searxng(item: dict[str, Any], freshness: WebSearchFreshness) -> WebSearchResult:
    url = str(item.get("url") or item.get("href") or "")
    return WebSearchResult(title=_bounded_text(item.get("title") or "Untitled result", 300), url=url, domain=_domain(url), snippet=_bounded_text(item.get("content") or item.get("body") or "", 800), freshness=freshness, published_at=item.get("publishedDate"))


def _result_from_ddgs(item: dict[str, Any], freshness: WebSearchFreshness) -> WebSearchResult:
    url = str(item.get("href") or item.get("url") or "")
    return WebSearchResult(title=_bounded_text(item.get("title") or "Untitled result", 300), url=url, domain=_domain(url), snippet=_bounded_text(item.get("body") or item.get("content") or "", 800), freshness=freshness)


def _bundle(query: WebSearchQuery, provider: str, rows: tuple[WebSearchResult, ...]) -> WebSearchGroundingBundle:
    refs = tuple(WebSearchEvidenceRef(evidence_id=f"web.evidence.{index + 1}", source_url=row.url, domain=row.domain, title=row.title, snippet=row.snippet, freshness=row.freshness) for index, row in enumerate(rows))
    return WebSearchGroundingBundle(query=query, provider=provider, results=rows, evidence_refs=refs)


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or "unknown"


def _bounded_text(value: object, limit: int) -> str:
    text = str(value)
    return text[:limit]


def _validate_fetch_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("web.fetch only supports absolute http(s) URLs")
    host = parsed.hostname or ""
    if _is_private_host(host):
        raise ValueError("web.fetch cannot fetch loopback or private-network URLs")
    return cleaned


def _is_private_host(host: str) -> bool:
    lowered = host.lower()
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _html_title(html: str) -> str:
    match = _TITLE_RE.search(html or "")
    if not match:
        return ""
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return _bounded_text(title, 300)


# ---------------------------------------------------------------------------
# Freshness policy
# ---------------------------------------------------------------------------

class FreshnessDecision(CapabilityRuntimeModel):
    freshness_needed: bool
    source_is_stale: bool
    recommended_freshness: WebSearchFreshness
    reason_code: str
    stale_threshold_days: int
    raw_source_persisted: bool = False


class FreshnessPolicy(CapabilityRuntimeModel):
    dependency_docs_stale_days: int = 14
    price_stale_days: int = 1
    memory_stale_days: int = 180
    default_stale_days: int = 30

    @classmethod
    def default(cls) -> "FreshnessPolicy":
        return cls()

    def evaluate(self, *, query: str, source_type: str, source_timestamp: datetime | None) -> FreshnessDecision:
        lowered = query.lower()
        source = source_type.lower()
        implicit_current = any(marker in lowered for marker in ("compatible", "version", "sdk", "api", "docs", "price", "current status", "release"))
        if source in {"dependency_docs", "api_docs", "library_docs"} or any(marker in lowered for marker in ("sdk", "api", "docs", "version", "compatible")):
            threshold = self.dependency_docs_stale_days
            freshness = WebSearchFreshness.CURRENT
            reason = "freshness.current_dependency_or_docs"
        elif "price" in lowered or source == "price":
            threshold = self.price_stale_days
            freshness = WebSearchFreshness.CURRENT
            reason = "freshness.current_price"
        elif source == "memory":
            threshold = self.memory_stale_days
            freshness = WebSearchFreshness.ANY
            reason = "freshness.memory_not_current"
        else:
            threshold = self.default_stale_days
            freshness = WebSearchFreshness.RECENT if implicit_current else WebSearchFreshness.ANY
            reason = "freshness.recent_or_any"
        stale = False
        if source_timestamp is not None:
            timestamp = source_timestamp if source_timestamp.tzinfo else source_timestamp.replace(tzinfo=UTC)
            stale = (datetime.now(UTC) - timestamp).days > threshold
        needed = (implicit_current or freshness == WebSearchFreshness.CURRENT) and (source != "memory" or stale)
        return FreshnessDecision(freshness_needed=needed, source_is_stale=stale, recommended_freshness=freshness, reason_code=reason, stale_threshold_days=threshold)
