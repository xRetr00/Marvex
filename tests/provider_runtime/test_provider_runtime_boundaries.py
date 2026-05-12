from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def python_sources(relative_path: str) -> list[Path]:
    root = ROOT / relative_path
    return sorted(root.rglob("*.py"))


def test_cli_source_uses_runtime_composition_and_not_provider_runtime_or_adapters():
    source = read_text("apps/cli/main.py")
    source_without_approved_lmstudio_bridge = source.replace(
        "run_lmstudio_responses_assistant_bridge", ""
    ).replace(
        "_run_assistant_runtime_lmstudio_responses_proof", ""
    ).replace(
        "assistant_runtime_lmstudio_responses", ""
    ).replace(
        "--assistant-runtime-lmstudio-responses", ""
    )

    assert "from packages.runtime_composition import (" in source
    assert "run_provider_foundation_turn" in source
    assert "run_fake_provider_assistant_bridge" in source
    assert "run_lmstudio_responses_assistant_bridge" in source
    assert "packages.provider_runtime" not in source
    assert "ProviderRuntimeConfig" not in source
    assert "create_provider" not in source
    assert "packages.adapters" not in source
    assert "FakeProvider" not in source
    assert "LiteLLMProvider" not in source
    assert "LMStudioResponsesProvider" not in source
    assert "lmstudio_responses" not in source_without_approved_lmstudio_bridge
    assert "_create_provider_for_cli_bootstrap" not in source


def test_core_source_does_not_import_provider_runtime_or_adapters():
    for path in python_sources("packages/core"):
        source = path.read_text(encoding="utf-8")

        assert "packages.provider_runtime" not in source
        assert "packages.adapters" not in source


def test_provider_runtime_python_source_does_not_import_core():
    for path in python_sources("packages/provider_runtime"):
        source = path.read_text(encoding="utf-8")

        assert "packages.core" not in source


def test_provider_port_source_contains_no_concrete_provider_names():
    source = read_text("packages/ports/provider/provider_port.py").lower()
    forbidden = [
        "fake",
        "litellm",
        "lmstudio",
        "lm studio",
        "openai",
        "openrouter",
        "anthropic",
        "gemini",
    ]

    assert [token for token in forbidden if token in source] == []


def test_provider_runtime_python_source_has_no_forbidden_runtime_logic_tokens():
    forbidden = [
        "registry",
        "plugin",
        "fallback",
        "retry",
        "session",
        "history",
        "routing",
        "health",
        "daemon",
        "server",
        "stream",
        "memory",
        "intent",
        "voice",
        "desktop",
        "tool",
        "mcp",
    ]

    for path in python_sources("packages/provider_runtime"):
        source = path.read_text(encoding="utf-8").lower()

        assert [token for token in forbidden if token in source] == []


def test_provider_runtime_source_allows_only_approved_provider_adapter_imports():
    source = read_text("packages/provider_runtime/provider_runtime.py")

    assert "from packages.adapters.providers.fake import FakeProvider" in source
    assert "from packages.adapters.providers.litellm import LiteLLMProvider" in source
    assert (
        "from packages.adapters.providers.lmstudio_responses import "
        "LMStudioResponsesProvider"
    ) in source
    assert "packages.adapters.providers." in source
