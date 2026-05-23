from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.context_runtime import ContextPack, SafeContextProjection
from packages.intent_runtime import SafeIntentProjection
from packages.prompt_harness_runtime import PromptAssemblyResult, SafePromptProjection
from packages.web_search_runtime import WebSearchEvidenceRef, WebSearchGroundingBundle


class CognitionStep(CapabilityRuntimeModel):
    step_id: str = Field(..., min_length=1)
    step_kind: Literal[
        "plan",
        "provider",
        "tool",
        "approval",
        "web_search",
        "grounded_answer",
        "clarify",
        "block",
        "finalize",
    ]
    required: bool = True
    reason_code: str = Field(..., min_length=1)
    raw_payload_persisted: Literal[False] = False


class CognitionStepPlan(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    steps: tuple[CognitionStep, ...]
    max_steps: int = Field(default=5, ge=1, le=6)
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "step_count": len(self.steps),
            "max_steps": self.max_steps,
            "step_kinds": tuple(step.step_kind for step in self.steps),
            "raw_payload_persisted": False,
        }


class CognitionEvidenceRef(CapabilityRuntimeModel):
    ref_type: Literal["web_evidence", "memory_evidence"]
    ref_id: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    raw_content_persisted: Literal[False] = False


class SafeCognitionProjection(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    intent_kind: str
    context_included_count: int
    prompt_section_count: int
    planned_step_count: int
    web_search_required: bool
    grounding_required: bool
    evidence_ref_count: int
    raw_prompt_persisted: Literal[False] = False
    raw_context_persisted: Literal[False] = False
    raw_payload_persisted: Literal[False] = False


class CognitionTurnAssembly(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    intent_projection: SafeIntentProjection
    context_pack: ContextPack
    context_projection: SafeContextProjection
    prompt_result: PromptAssemblyResult
    prompt_projection: SafePromptProjection
    provider_prompt_payload: Any | None = None
    intent_plan: Any
    step_plan: CognitionStepPlan
    evidence_refs: tuple[CognitionEvidenceRef, ...] = ()
    web_evidence_refs: tuple[WebSearchEvidenceRef, ...] = ()
    memory_evidence_refs: tuple[Any, ...] = ()
    web_search_bundle: WebSearchGroundingBundle | None = None
    web_search_required: bool = False
    grounding_required: bool = False
    raw_prompt_persisted: Literal[False] = False
    raw_context_persisted: Literal[False] = False
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> SafeCognitionProjection:
        return SafeCognitionProjection(
            schema_version=self.schema_version,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            intent_kind=str(self.intent_projection.selected_intent["intent_kind"]),
            context_included_count=self.context_projection.included_count,
            prompt_section_count=self.prompt_projection.section_count,
            planned_step_count=len(self.step_plan.steps),
            web_search_required=self.web_search_required,
            grounding_required=self.grounding_required,
            evidence_ref_count=len(self.evidence_refs),
        )
