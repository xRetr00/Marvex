from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSISTANT_RUNTIME_ROOT = ROOT / "packages" / "assistant_runtime"

FORBIDDEN_IMPORT_PREFIXES = (
    "packages.core",
    "packages.provider_runtime",
    "packages.adapters",
    "packages.ports",
    "apps.cli",
    "services",
)
FORBIDDEN_IMPORT_PARTS = (
    "tool",
    "tools",
    "memory",
    "voice",
    "ui",
    "desktop",
    "proactive",
)
FORBIDDEN_PROVIDER_NAMES = (
    "LM Studio",
    "LMStudio",
    "litellm",
    "LiteLLM",
    "OpenAI",
    "OpenRouter",
    "Anthropic",
    "Gemini",
)
FORBIDDEN_PROVIDER_BRIDGE_TERMS = (
    "ProviderRequest",
    "ProviderResponse",
    "TurnInput",
    "TurnOutput",
    "provider_response_id",
    "provider bridge",
    "provider routing",
    "provider fallback",
    "model routing",
)
PROVIDER_BRIDGE_TERM_ALLOWLIST = {
    "packages/assistant_runtime/structured_output_consumer.py": {
        "provider_response_id",
    },
}
FORBIDDEN_SUBSYSTEM_BEHAVIOR_TERMS = (
    "memory runtime",
    "tool runtime",
    "voice runtime",
    "desktop agent",
    "ui shell",
    "proactive behavior",
    "http server",
    "ipc daemon",
    "service daemon",
)


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _read_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return None
        return node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _import_violates(module: str | None) -> bool:
    if module is None:
        return False
    lowered_parts = {part.lower() for part in module.split(".")}
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    ) or bool(lowered_parts.intersection(FORBIDDEN_IMPORT_PARTS))


def _scan_imports(paths: list[Path], failures: list[str]) -> None:
    for path in paths:
        for node in ast.walk(_read_tree(path)):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if _import_violates(module):
                failures.append(f"{_rel(path)} imports forbidden boundary: {module}")
            for alias in node.names:
                if alias.name in FORBIDDEN_PROVIDER_BRIDGE_TERMS:
                    failures.append(
                        f"{_rel(path)} imports provider-bridge contract: {alias.name}"
                    )


def _scan_text(paths: list[Path], failures: list[str]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        rel = _rel(path)
        allowed_terms = PROVIDER_BRIDGE_TERM_ALLOWLIST.get(rel, set())
        for name in FORBIDDEN_PROVIDER_NAMES:
            if name.lower() in lowered:
                failures.append(f"{rel} mentions concrete provider: {name}")
        for term in FORBIDDEN_SUBSYSTEM_BEHAVIOR_TERMS:
            if term in lowered:
                failures.append(f"{rel} mentions future subsystem behavior: {term}")
        for term in FORBIDDEN_PROVIDER_BRIDGE_TERMS:
            if term in allowed_terms:
                continue
            pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])")
            if pattern.search(text):
                failures.append(f"{rel} mentions provider-bridge term: {term}")


def main() -> int:
    failures: list[str] = []
    paths = _python_files(ASSISTANT_RUNTIME_ROOT)

    _scan_imports(paths, failures)
    _scan_text(paths, failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS assistant runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
