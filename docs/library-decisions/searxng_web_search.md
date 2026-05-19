# Library Decision: SearXNG Web Search Adapter

library name: SearXNG HTTP JSON API

official source: https://docs.searxng.org/dev/search_api.html and https://github.com/searxng/searxng

maintenance status: Active as of May 19, 2026. Marvex does not vendor or run SearXNG in this goal; it implements a compatible HTTP/JSON adapter for a user-configured local or self-hosted base URL.

why use it: SearXNG is a free/open-source metasearch service that can be self-hosted and does not require a paid search API key by default. It fits Marvex's local-first search boundary when configured explicitly.

why not custom code: Custom metasearch would recreate query normalization, result aggregation, provider support, and abuse controls. Marvex should own policy and safe projections, not search-engine implementation.

fallback if abandoned: Fall back to DDGS when available, or report `web_search_provider_unavailable` until another approved backend is configured.

pyproject dependency: none; HTTP client support is already present transitively through the resolved Marvex stack.

declared dependency: none; adapter uses configured SearXNG HTTP JSON API and existing `httpx` availability.

verified date: 2026-05-19

verified by: Codex

scope: Adopted as an adapter path in `packages.web_search_runtime.SearXNGWebSearchAdapter`. It calls `/search` with `format=json`, parses public result metadata, and projects safe evidence refs. It stores no API key by default and persists no raw response payload.

architecture fit: Preferred web search provider when configured. It supports read/list/search and grounded evidence without handing browser automation, account access, or policy to the search backend.

adopt / defer / reject decision: Adopt adapter, not bundled service. Tests use mocked HTTP/JSON responses so validation is deterministic and does not require a running SearXNG instance.

risks: Requires an external/self-hosted endpoint. Search results are untrusted public data and must be treated as evidence candidates, not authoritative truth.
