import ast
from pathlib import Path


def test_assistant_runtime_import_boundary():
    forbidden_import_roots = (
        "packages.core",
        "packages.provider_runtime",
        "packages.adapters",
        "packages.ports",
        "apps.cli",
        "services",
    )
    forbidden_provider_names = (
        "lmstudio",
        "litellm",
        "openai",
        "openrouter",
        "anthropic",
        "gemini",
    )
    forbidden_domain_import_parts = (
        "tool",
        "memory",
        "voice",
        "ui",
        "desktop",
        "proactive",
    )

    for path in Path("packages/assistant_runtime").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module_name = None
            if isinstance(node, ast.ImportFrom):
                module_name = node.module
            elif isinstance(node, ast.Import):
                module_name = node.names[0].name
            if module_name is None:
                continue

            lowered = module_name.lower()
            assert not lowered.startswith(forbidden_import_roots)
            assert not any(name in lowered for name in forbidden_provider_names)
            assert not any(
                f".{part}" in lowered or lowered.endswith(f".{part}")
                for part in forbidden_domain_import_parts
            )
