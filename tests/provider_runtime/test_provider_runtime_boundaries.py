from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def python_sources(relative_path: str) -> list[Path]:
    root = ROOT / relative_path
    return sorted(root.rglob("*.py"))


def test_cli_source_uses_provider_runtime_and_not_concrete_adapters():
    source = read_text("apps/cli/main.py")

    assert "from packages.provider_runtime import ProviderRuntimeConfig, create_provider" in source
    assert "packages.adapters" not in source
    assert "FakeProvider" not in source
    assert "LiteLLMProvider" not in source
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
        "lmstudio",
    ]

    for path in python_sources("packages/provider_runtime"):
        source = path.read_text(encoding="utf-8").lower()

        assert [token for token in forbidden if token in source] == []
