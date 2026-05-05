from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "packages" / "provider_structured_output"

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
    if not PACKAGE_ROOT.exists():
        return []
    return sorted(path for path in PACKAGE_ROOT.rglob("*.py") if path.is_file())


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return None
        return node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def main() -> int:
    failures: list[str] = []

    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            if any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ):
                failures.append(f"{_rel(path)} imports forbidden boundary: {module}")

        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for term in FORBIDDEN_TEXT:
            if term.lower() in lowered:
                failures.append(f"{_rel(path)} contains forbidden term: {term}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS provider structured output boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
