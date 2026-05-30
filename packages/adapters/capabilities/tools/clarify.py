"""Clarify tool — lets the MODEL ask the user a disambiguation question.

This is a *control* tool, not a capability: the agentic loop intercepts a call to
it (by id) and pauses the turn to surface the question in the UI (QuestionTool)
instead of executing anything. The model decides when a request is ambiguous and
calls this itself - clarification is model-driven, not a brittle backend keyword
match. ``execute`` exists only as a harmless fallback for the Tool ABC.
"""

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

CLARIFY_TOOL_ID = "clarify"


class ClarifyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=300, description="The clarifying question to ask the user.")
    options: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Optional short answer choices to offer. The user can always type a custom answer.",
    )


class ClarifyTool(Tool):
    id: ClassVar[str] = CLARIFY_TOOL_ID
    name: ClassVar[str] = "Ask the user"
    description: ClassVar[str] = (
        "Ask the user a brief clarifying question when their request is ambiguous and you cannot "
        "safely proceed (e.g. an ambiguous name, missing detail, or two plausible meanings). "
        "Provide the question and optional short answer choices. The turn pauses for the user's reply."
    )
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = ClarifyParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = ClarifyParams(**request.arguments)
        return succeeded_result(request, {"question": params.question, "options": list(params.options)})


def clarification_payload_from_arguments(arguments: dict[str, object]) -> dict[str, object]:
    """Build the UI clarification payload (QuestionTool shape) from a clarify call."""

    try:
        params = ClarifyParams(**arguments)
    except Exception:
        question = str(arguments.get("question") or "Could you clarify your request?")
        raw_options = arguments.get("options")
        options = [str(option) for option in raw_options] if isinstance(raw_options, list) else []
        params = ClarifyParams(question=question[:300], options=options[:6])
    return {
        "kind": "single" if params.options else "text",
        "title": params.question,
        "allow_custom": True,
        "options": [
            {"id": f"opt_{index}", "label": label, "description": ""}
            for index, label in enumerate(params.options)
        ],
    }


__all__ = ["ClarifyTool", "ClarifyParams", "CLARIFY_TOOL_ID", "clarification_payload_from_arguments"]
