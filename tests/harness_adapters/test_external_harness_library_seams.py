from packages.adapters.prompt_harness.external_seams import (
    DisabledHarnessLibraryBackend,
    HarnessBackendStatus,
    HarnessExternalAdapterConfig,
    HarnessExternalBackend,
)


def test_external_harness_library_seams_are_disabled_and_policy_safe() -> None:
    for backend in HarnessExternalBackend:
        config = HarnessExternalAdapterConfig(schema_version="1", backend=backend, status=HarnessBackendStatus.ADAPTER_SEAM_READY, reason_code="dependency_deferred")
        capabilities = DisabledHarnessLibraryBackend(config=config).safe_capabilities()

        assert capabilities["backend"] == backend.value
        assert capabilities["library_owns_policy"] is False
        assert capabilities["raw_prompt_access_allowed"] is False
        assert capabilities["automatic_retry_allowed"] is False
        assert capabilities["autonomous_loop_allowed"] is False
