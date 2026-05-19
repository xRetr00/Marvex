# Web Search Runtime

Marvex now has a real `packages.web_search_runtime` for safe public web search and grounded evidence preparation.

Runtime models:

- `WebSearchQuery`
- `WebSearchResult`
- `WebSearchEvidenceRef`
- `WebSearchFreshness`
- `WebSearchGroundingBundle`
- `SafeWebSearchProjection` through model `safe_projection()` methods

Providers:

- `SearXNGWebSearchAdapter` is preferred when a base URL is configured. It calls the HTTP JSON `/search` API with `format=json`, requires no API key by default, and parses title, URL, domain, snippet, and freshness metadata.
- `DDGSWebSearchAdapter` is the fallback when configured or injected. It uses the real `ddgs` package behind the adapter boundary.
- `WebSearchProviderSelector` chooses SearXNG first, then DDGS, and otherwise raises `web_search_provider_unavailable`.

Allowed by default:

- public web search
- public result listing
- safe snippets
- title, URL, domain, freshness, and source metadata

Requires approval:

- downloading files
- submitting forms
- logging into sites
- sending, uploading, or exporting data
- browser actions with side effects

Blocked/hard unsafe:

- CAPTCHA or anti-bot bypass
- stealth scraping
- credential extraction
- exfiltration
- account abuse
- destructive or payment actions without explicit consent

Search results are untrusted evidence candidates. PromptHarnessRuntime may receive safe evidence sections only; raw pages, raw provider payloads, raw DOM, screenshots, credentials, and hidden account data must not be persisted or injected by default.
