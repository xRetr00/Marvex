"""Uniform built-in tool interface.

Every built-in tool is a self-contained module exposing one ``Tool`` subclass:
its id, model-facing name/description, risk + side-effect metadata, a pydantic
``params_model`` (the single source of truth for its argument schema), and an
``execute`` that takes a ``CapabilityExecutionRequest`` and returns a
``CapabilityResultEnvelope``.

This replaces the old ``if/elif`` dispatch ladders in ``builtins.py`` and
``files.py``. The ``params_model`` is what makes model-driven tool-calling
(see docs/TODO/02) tractable: ``json_schema()`` derives the tool's parameter
schema directly from it, so there is one place that describes a tool's inputs
instead of three (pydantic request model + regex slot parser + dispatch branch).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityManifest,
    CapabilityRef,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


class Tool(ABC):
    """Base class for a single built-in tool.

    Subclasses set the class-level metadata attributes and implement
    ``execute``. Keep one tool per module.
    """

    #: Stable capability identifier, e.g. "calculator" -> ref "builtin.calculator".
    id: ClassVar[str]
    #: Human/model-facing short name.
    name: ClassVar[str]
    #: One-sentence, model-facing description of what the tool does.
    description: ClassVar[str]
    #: Risk + side-effect classification used by the policy/approval boundary.
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    #: pydantic model describing the tool's arguments (single source of truth).
    params_model: ClassVar[type[BaseModel]]
    #: Identifier prefix; built-ins use "builtin.", file tools use "file.".
    ref_prefix: ClassVar[str] = "builtin."
    schema_version: ClassVar[str] = "1"

    def capability_ref(self) -> CapabilityRef:
        return CapabilityRef(kind=CapabilityKind.TOOL, identifier=self.identifier())

    @classmethod
    def identifier(cls) -> str:
        return f"{cls.ref_prefix}{cls.id}"

    def json_schema(self) -> dict[str, object]:
        """JSON schema for the tool's parameters, for model tool-calling."""

        return self.params_model.model_json_schema()

    def to_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            schema_version=self.schema_version,
            capability_ref=self.capability_ref(),
            display_name=self.name,
            description=self.description,
            owner_package="packages.adapters.capabilities.tools",
            adapter_boundary="builtin_tools_foundation",
            permissions=(f"tool.{self.identifier()}",),
            input_schema=self.json_schema(),
            metadata={
                "risk_level": self.risk_level.value,
                "side_effect_level": self.side_effect_level.value,
                "shell_execution_allowed": False,
                "file_write_allowed": self.side_effect_level
                is not ToolSideEffectLevel.READ_ONLY,
                "network_fetch_allowed": False,
            },
            enabled_by_default=False,
        )

    @abstractmethod
    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        """Run the tool for an (already policy-checked) execution request."""
        raise NotImplementedError


def succeeded_result(
    request: CapabilityExecutionRequest, safe_result: dict[str, object]
) -> CapabilityResultEnvelope:
    return CapabilityResultEnvelope(
        schema_version=request.schema_version,
        result_id=f"{request.request_id}:result",
        trace_id=request.trace_id,
        turn_id=request.turn_id,
        capability_ref=request.proposal.capability_ref,
        status="succeeded",
        safe_result=safe_result,
        raw_input_persisted=False,
        raw_output_persisted=False,
    )


def denied_result(
    request: CapabilityExecutionRequest, *, reason_code: str
) -> CapabilityResultEnvelope:
    return CapabilityResultEnvelope(
        schema_version=request.schema_version,
        result_id=f"{request.request_id}:result",
        trace_id=request.trace_id,
        turn_id=request.turn_id,
        capability_ref=request.proposal.capability_ref,
        status="denied",
        safe_result={"reason_code": reason_code},
        raw_input_persisted=False,
        raw_output_persisted=False,
    )


__all__ = ["Tool", "succeeded_result", "denied_result"]
