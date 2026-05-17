from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSISTANT_RUNTIME_ROOT = ROOT / "packages" / "assistant_runtime"

FORBIDDEN_IMPORT_PREFIXES = (
    "packages.core",
    "packages.local_api",
    "packages.local_service_startup",
    "packages.provider_runtime",
    "packages.adapters",
    "packages.ports",
    "packages.runtime_composition",
    "packages.telemetry",
    "apps.cli",
    "services",
)
ASSISTANT_RUNTIME_IMPORT_ALLOWLIST = {
    "packages/assistant_runtime/provider_stage.py": {"packages.telemetry"},
    "packages/assistant_runtime/structured_output_turn_result.py": {
        "packages.telemetry"
    },
}
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
    "packages/assistant_runtime/lifecycle.py": {
        "provider_response_id",
    },
    "packages/assistant_runtime/provider_stage.py": {
        "ProviderRequest",
        "ProviderResponse",
    },
    "packages/assistant_runtime/structured_output_consumer.py": {
        "provider_response_id",
    },
}
STRUCTURED_OUTPUT_SEAM_FILES = {
    "packages/assistant_runtime/structured_output_consumer.py",
    "packages/assistant_runtime/structured_output_runtime_entry.py",
}
STRUCTURED_OUTPUT_SEAM_FORBIDDEN_IMPORT_PREFIXES = FORBIDDEN_IMPORT_PREFIXES + (
    "packages.provider_structured_output",
    "packages.contracts",
)
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
STATE_PRIMITIVE_NAMES = (
    "AssistantStageName",
    "AssistantStageResult",
    "AssistantTurnLifecycleSummary",
    "TurnStateSnapshot",
    "AssistantTurnExecutionSummary",
    "StateTransitionRecord",
)
STATE_OWNER_FORBIDDEN_ROOTS = (
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "local_service_startup",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "telemetry",
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


def _import_violates(module: str | None, prefixes: tuple[str, ...]) -> bool:
    if module is None:
        return False
    lowered_parts = {part.lower() for part in module.split(".")}
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in prefixes
    ) or bool(lowered_parts.intersection(FORBIDDEN_IMPORT_PARTS))


def _import_allowed(rel: str, module: str | None) -> bool:
    if module is None:
        return False
    return any(
        module == allowed or module.startswith(f"{allowed}.")
        for allowed in ASSISTANT_RUNTIME_IMPORT_ALLOWLIST.get(rel, set())
    )


def _scan_imports(paths: list[Path], failures: list[str]) -> None:
    for path in paths:
        rel = _rel(path)
        forbidden_import_prefixes = (
            STRUCTURED_OUTPUT_SEAM_FORBIDDEN_IMPORT_PREFIXES
            if rel in STRUCTURED_OUTPUT_SEAM_FILES
            else FORBIDDEN_IMPORT_PREFIXES
        )
        for node in ast.walk(_read_tree(path)):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if _import_allowed(rel, module):
                continue
            if _import_violates(module, forbidden_import_prefixes):
                failures.append(f"{rel} imports forbidden boundary: {module}")
            for alias in node.names:
                if (
                    alias.name in FORBIDDEN_PROVIDER_BRIDGE_TERMS
                    and alias.name not in PROVIDER_BRIDGE_TERM_ALLOWLIST.get(rel, set())
                ):
                    failures.append(
                        f"{rel} imports provider-bridge contract: {alias.name}"
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


def _scan_state_primitive_ownership(failures: list[str]) -> None:
    for root in STATE_OWNER_FORBIDDEN_ROOTS:
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            rel = _rel(path)
            for name in STATE_PRIMITIVE_NAMES:
                if name in text:
                    failures.append(
                        f"{rel} mentions AssistantRuntime state primitive: {name}"
                    )


def main() -> int:
    failures: list[str] = []
    paths = _python_files(ASSISTANT_RUNTIME_ROOT)

    _scan_imports(paths, failures)
    _scan_text(paths, failures)
    _scan_state_primitive_ownership(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS assistant runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
