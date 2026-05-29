"""Repo status tool — injected read-only repository status snapshot."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from .base import Tool, succeeded_result


class RepoStatusParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branch: str = Field(default="unknown", max_length=120)
    clean: bool = True
    short_status: str = Field(default="", max_length=4000)


class RepoStatusTool(Tool):
    id: ClassVar[str] = "repo_status"
    name: ClassVar[str] = "Repo Status"
    description: ClassVar[str] = "Report a read-only snapshot of repository branch and cleanliness."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = RepoStatusParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = RepoStatusParams(
            branch=str(request.arguments.get("branch") or "unknown").strip() or "unknown",
            clean=bool(request.arguments.get("clean", True)),
            short_status=str(request.arguments.get("short_status") or ""),
        )
        return succeeded_result(
            request,
            {
                "branch": params.branch,
                "clean": params.clean,
                "status_length": len(params.short_status),
            },
        )


__all__ = ["RepoStatusTool", "RepoStatusParams"]
