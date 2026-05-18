from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.prompt_harness_runtime import HarnessValidationResult


class GuardrailsAdapterConfig(CapabilityRuntimeModel):
    schema_version: str
    backend_enabled: bool
    backend_name: str = "guardrails_ai"
    automatic_retries_allowed: Literal[False] = False
    raw_prompt_validation_allowed: Literal[False] = False


class DisabledGuardrailsBackend:
    def __init__(self, *, reason_code: str) -> None:
        self.reason_code = reason_code
        self.backend_name = "disabled_guardrails"

    def validate(self, safe_projection: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return True, (self.reason_code, "safe_projection_only")


class PromptHarnessGuardrailsAdapter:
    def __init__(self, *, config: GuardrailsAdapterConfig, backend: DisabledGuardrailsBackend) -> None:
        self.config = config
        self.backend = backend

    def validate_safe_projection(self, safe_projection: dict[str, Any]) -> HarnessValidationResult:
        valid, reason_codes = self.backend.validate({key: value for key, value in safe_projection.items() if not str(key).lower().startswith("raw")})
        return HarnessValidationResult(
            schema_version=self.config.schema_version,
            trace_id="trace-harness-validation",
            turn_id="turn-harness-validation",
            valid=valid,
            reason_codes=reason_codes,
            validator_backend=self.backend.backend_name,
            prompt_section_count=int(safe_projection.get("prompt_section_count", 0)) if isinstance(safe_projection.get("prompt_section_count", 0), int) else 0,
        )
