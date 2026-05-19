# Library Decision: DDGS Web Search

library name: DDGS

official source: https://github.com/deedy5/ddgs

maintenance status: Active as of May 19, 2026. uv resolved `ddgs==9.14.4` with the current Marvex stack and `uv run python -m pip check` remained clean after installation.

why use it: Marvex needs a free/open-source fallback web search backend when a local SearXNG base URL is not configured. DDGS provides a maintained Python search library that can be isolated behind `packages.web_search_runtime.DDGSWebSearchAdapter`.

why not custom code: Custom scraping or search aggregation would create brittle provider-specific behavior and higher abuse risk. A maintained package keeps the backend replaceable and makes the adapter boundary explicit.

fallback if abandoned: Keep SearXNG as preferred configured backend. If DDGS breaks or becomes unsafe, disable the adapter and require a configured SearXNG provider or a future approved search backend.

pyproject dependency: ddgs

declared dependency: ddgs>=9.14.4

verified date: 2026-05-19

verified by: Codex

scope: Adopted behind `packages.web_search_runtime.DDGSWebSearchAdapter`. The adapter returns safe result/evidence models only. It must not download files, submit forms, log into accounts, bypass anti-bot systems, persist raw pages, or execute browser actions.

architecture fit: Good fallback for public read/search/list behavior. CapabilityRuntime and risk governance remain authoritative for side effects and approvals.

adopt / defer / reject decision: Adopt. Tests use mocked DDGS clients plus import-backed package proof so default validation does not rely on live public search.

risks: Search-provider behavior can drift, results may be noisy, and some environments may block external search. Marvex must treat returned snippets as untrusted evidence and validate citations against evidence refs.
