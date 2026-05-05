from __future__ import annotations

import ast
from pathlib import Path


PACKAGE_ROOT = Path("packages/provider_structured_output")

FORBIDDEN_IMPORT_PREFIXES = (
    "packages.core",
    "packages.assistant_runtime",
    "packages.provider_runtime",
    "packages.adapters",
    "packages.ports",
    "apps.cli",
    "services",
)

FORBIDDEN_TEXT = (
    "LM Studio",
    "LMStudio",
    "LiteLLM",
    "OpenAI",
    "OpenRouter",
    "Anthropic",
    "Gemini",
    "Promptify",
    "Instructor",
    "Outlines",
    "Guidance",
    "LangGraph",
    "Pydantic AI",
    "provider_response_id",
    "render_prompt",
    "prompt template",
)


def _python_files() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def test_import_boundary_allows_only_contracts_and_pydantic():
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            else:
                continue

            assert not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            )


def test_no_concrete_providers_frameworks_or_prompt_terms_in_package_source():
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for term in FORBIDDEN_TEXT:
            assert term.lower() not in lowered
