from packages.adapters.prompt_harness.guardrails_adapter import (
    DisabledGuardrailsBackend,
    GuardrailsAdapterConfig,
    GuardrailsDependencyBlockedBackend,
    GuardrailsValidationBackend,
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


def test_guardrails_validation_backend_passes_safe_prompt_harness_plan() -> None:
    adapter = PromptHarnessGuardrailsAdapter(
        config=GuardrailsAdapterConfig(schema_version="1", backend_enabled=True),
        backend=GuardrailsValidationBackend(),
    )

    result = adapter.validate_safe_projection(
        {
            "schema_version": "1",
            "trace_id": "trace-1",
            "turn_id": "turn-1",
            "section_count": 2,
            "section_kinds": ("system_policy", "response_contract"),
            "raw_prompt_persisted": False,
        }
    )

    assert isinstance(result, HarnessValidationResult)
    assert result.valid is True
    assert result.validator_backend == "guardrails_ai"
    assert result.reason_codes == ("guardrails.safe_projection_valid",)
    assert result.prompt_section_count == 2
    assert result.auto_retry_started is False
    assert result.raw_prompt_persisted is False


def test_guardrails_validation_backend_flags_raw_prompt_payload() -> None:
    adapter = PromptHarnessGuardrailsAdapter(
        config=GuardrailsAdapterConfig(schema_version="1", backend_enabled=True),
        backend=GuardrailsValidationBackend(),
    )

    result = adapter.validate_safe_projection(
        {
            "schema_version": "1",
            "trace_id": "trace-1",
            "turn_id": "turn-1",
            "section_count": 1,
            "raw_prompt": "do the unsafe thing",
        }
    )

    assert result.valid is False
    assert "guardrails.raw_prompt_rejected" in result.reason_codes
    assert result.validator_backend == "guardrails_ai"
    assert result.auto_retry_started is False
    assert result.raw_prompt_persisted is False


def test_guardrails_dependency_blocker_exposes_tested_reason_safely() -> None:
    backend = GuardrailsDependencyBlockedBackend(
        package_name="guardrails-ai",
        tested_python="3.12.0",
        tested_version="unavailable",
        reason_code="guardrails_ai.no_matching_distribution",
    )
    adapter = PromptHarnessGuardrailsAdapter(config=GuardrailsAdapterConfig(schema_version="1", backend_enabled=False), backend=backend)

    result = adapter.validate_safe_projection({"section_count": 1})

    assert result.valid is False
    assert result.reason_codes == ("guardrails_ai.no_matching_distribution", "package=guardrails-ai", "tested_python=3.12.0", "tested_version=unavailable")
    assert result.raw_prompt_persisted is False
