"""Safe public webpage fetch tool for the agentic loop.

The tool retrieves a selected public result URL and returns bounded extracted
text. It is read-only network access: no forms, browser actions, downloads, or
raw HTML persistence.
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


class WebFetchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(..., min_length=1, max_length=1200, description="Absolute public http(s) URL to fetch.")
    max_chars: int = Field(default=4000, ge=1, le=8000, description="Maximum extracted text characters to return.")


class WebFetchTool(Tool):
    id: ClassVar[str] = "fetch"
    name: ClassVar[str] = "Web fetch"
    description: ClassVar[str] = "Fetch and extract readable text from a public URL, usually after web.search returns candidate sources."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.NETWORK
    params_model: ClassVar[type[BaseModel]] = WebFetchParams
    ref_prefix: ClassVar[str] = "web."

    def __init__(self, *, fetcher: Any | None = None) -> None:
        self._fetcher = fetcher

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        from packages.web_search_runtime import TrafilaturaWebFetchAdapter

        params = WebFetchParams(
            url=str(request.arguments.get("url") or "").strip(),
            max_chars=int(request.arguments.get("max_chars") or 4000),
        )
        fetcher = self._fetcher or TrafilaturaWebFetchAdapter()
        try:
            result = fetcher.fetch(params.url, max_chars=params.max_chars)
        except Exception as exc:
            return succeeded_result(
                request,
                {
                    "operation": "web_fetch",
                    "url": params.url,
                    "text_character_count": 0,
                    "text_preview": "",
                    "error": f"web fetch failed: {type(exc).__name__}",
                    "raw_html_persisted": False,
                    "raw_page_text_persisted": False,
                },
            )
        projection = result.safe_projection()
        return succeeded_result(
            request,
            {
                "operation": "web_fetch",
                **projection,
            },
        )


__all__ = ["WebFetchTool", "WebFetchParams"]
