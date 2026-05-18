from packages.adapters.prompt_harness.guardrails_adapter import (
    DisabledGuardrailsBackend,
    GuardrailsAdapterConfig,
    PromptHarnessGuardrailsAdapter,
)
from packages.prompt_harness_runtime import HarnessValidationResult


def test_guardrails_adapter_disabled_backend_returns_safe_validation_result() -> None:
    adapter = PromptHarnessGuardrailsAdapter(config=GuardrailsAdapterConfig(schema_version="1", backend_enabled=False), backend=DisabledGuardrailsBackend(reason_code="dependency_deferred"))

    result = adapter.validate_safe_projection({"prompt_section_count": 3})

    assert isinstance(result, HarnessValidationResult)
    assert result.valid is True
    assert result.validator_backend == "disabled_guardrails"
    assert result.raw_prompt_persisted is False


def test_guardrails_adapter_does_not_retry_or_rewrite_prompt() -> None:
    adapter = PromptHarnessGuardrailsAdapter(config=GuardrailsAdapterConfig(schema_version="1", backend_enabled=False, automatic_retries_allowed=False), backend=DisabledGuardrailsBackend(reason_code="dependency_deferred"))

    result = adapter.validate_safe_projection({"unsafe": "raw prompt text is not passed"})

    assert result.auto_retry_started is False
    assert result.raw_prompt_persisted is False
