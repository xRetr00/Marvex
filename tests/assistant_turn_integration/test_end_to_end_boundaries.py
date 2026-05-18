from pathlib import Path


def test_end_to_end_boundary_keeps_local_api_and_runtime_composition_thin() -> None:
    local_api_source = "\n".join(path.read_text(encoding="utf-8") for path in sorted((Path("packages") / "local_api").rglob("*.py")))
    runtime_composition_source = "\n".join(path.read_text(encoding="utf-8") for path in sorted((Path("packages") / "runtime_composition").rglob("*.py")))
    integration_source = "\n".join(path.read_text(encoding="utf-8") for path in sorted((Path("packages") / "assistant_turn_integration").rglob("*.py")))

    assert "packages.assistant_turn_integration" not in local_api_source
    assert "packages.assistant_turn_integration" not in runtime_composition_source
    assert "raw_prompt_persisted=True" not in integration_source
    assert "raw_payload_persisted=True" not in integration_source
    assert "model router" not in integration_source.lower()
