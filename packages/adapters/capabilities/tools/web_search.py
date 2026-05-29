"""Web search tool (web.search) for the agentic loop (docs/TODO/05 + 02).

Wraps an injected ``WebSearchProvider`` (Wikipedia / DDGS / SearXNG / multi)
so the model can search on demand and cite results, instead of relying on the
brittle pre-classified grounded-answer path that rejected good answers with
"evidence is missing". Read-only retrieval -> SAFE risk (auto-executes in the
loop), NETWORK side-effect.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from .base import Tool, succeeded_result


class WebSearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(..., min_length=1, max_length=400, description="What to search the web for.")
    max_results: int = Field(default=5, ge=1, le=10)


class WebSearchTool(Tool):
    id: ClassVar[str] = "search"
    name: ClassVar[str] = "Web search"
    description: ClassVar[str] = "Search the web and return result titles, URLs, and snippets to ground an answer."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.NETWORK
    params_model: ClassVar[type[BaseModel]] = WebSearchParams
    ref_prefix: ClassVar[str] = "web."

    def __init__(self, *, provider: Any) -> None:
        # provider implements WebSearchProvider.search(WebSearchQuery) -> bundle.
        self._provider = provider

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        from packages.web_search_runtime import WebSearchQuery

        params = WebSearchParams(
            query=str(request.arguments.get("query") or "").strip() or "(empty)",
            max_results=int(request.arguments.get("max_results") or 5),
        )
        try:
            bundle = self._provider.search(
                WebSearchQuery(query=params.query, max_results=params.max_results)
            )
        except Exception as exc:
            return succeeded_result(
                request,
                {
                    "operation": "web_search",
                    "query": params.query,
                    "result_count": 0,
                    "results": [],
                    "error": f"web search failed: {type(exc).__name__}",
                },
            )
        results = []
        for result in getattr(bundle, "results", ()) or ():
            results.append(
                {
                    "title": getattr(result, "title", ""),
                    "url": getattr(result, "url", ""),
                    "domain": getattr(result, "domain", ""),
                    "snippet": getattr(result, "snippet", "")[:400],
                }
            )
        evidence = [
            {"evidence_id": getattr(ref, "evidence_id", ""), "url": getattr(ref, "source_url", "")}
            for ref in getattr(bundle, "evidence_refs", ()) or ()
        ]
        return succeeded_result(
            request,
            {
                "operation": "web_search",
                "query": params.query,
                "provider": getattr(bundle, "provider", "unknown"),
                "result_count": len(results),
                "results": results,
                "evidence_refs": evidence,
            },
        )


__all__ = ["WebSearchTool", "WebSearchParams"]
