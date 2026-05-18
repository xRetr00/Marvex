from __future__ import annotations

import importlib.util
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


class GuardrailsValidationBackend:
    backend_name = "guardrails_ai"

    def __init__(self, *, importer: Any = importlib.util.find_spec) -> None:
        self._library_available = importer("guardrails") is not None

    def validate(self, safe_projection: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        unsafe_keys = tuple(
            key
            for key, value in safe_projection.items()
            if str(key).lower().startswith("raw") and value is not False
        )
        if unsafe_keys:
            return False, ("guardrails.raw_prompt_rejected",)
        if safe_projection.get("raw_prompt_persisted") is not False and "raw_prompt_persisted" in safe_projection:
            return False, ("guardrails.raw_prompt_persistence_rejected",)
        section_count = safe_projection.get("section_count", safe_projection.get("prompt_section_count", 0))
        if not isinstance(section_count, int) or section_count < 0:
            return False, ("guardrails.invalid_section_count",)
        return True, ("guardrails.safe_projection_valid",)


class GuardrailsDependencyBlockedBackend:
    backend_name = "guardrails_ai_blocked"

    def __init__(self, *, package_name: str, tested_python: str, tested_version: str, reason_code: str) -> None:
        self.package_name = package_name
        self.tested_python = tested_python
        self.tested_version = tested_version
        self.reason_code = reason_code

    def validate(self, _safe_projection: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return False, (
            self.reason_code,
            f"package={self.package_name}",
            f"tested_python={self.tested_python}",
            f"tested_version={self.tested_version}",
        )


class PromptHarnessGuardrailsAdapter:
    def __init__(self, *, config: GuardrailsAdapterConfig, backend: DisabledGuardrailsBackend | GuardrailsValidationBackend | GuardrailsDependencyBlockedBackend) -> None:
        self.config = config
        self.backend = backend

    def validate_safe_projection(self, safe_projection: dict[str, Any]) -> HarnessValidationResult:
        valid, reason_codes = self.backend.validate(dict(safe_projection))
        section_count = safe_projection.get("section_count", safe_projection.get("prompt_section_count", 0))
        return HarnessValidationResult(
            schema_version=self.config.schema_version,
            trace_id=str(safe_projection.get("trace_id", "trace-harness-validation")),
            turn_id=str(safe_projection.get("turn_id", "turn-harness-validation")),
            valid=valid,
            reason_codes=reason_codes,
            validator_backend=self.backend.backend_name,
            prompt_section_count=section_count if isinstance(section_count, int) else 0,
        )
