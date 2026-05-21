from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COGNITION = ROOT / "packages" / "cognition_runtime"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "contextlib",
    "dataclasses",
    "datetime",
    "io",
    "pathlib",
    "packages.cognition_runtime",
    "packages.capability_runtime",
    "packages.connector_runtime",
    "packages.contracts",
    "packages.context_runtime",
    "packages.grounded_answer_runtime",
    "packages.intent_runtime",
    "packages.memory_runtime",
    "packages.memory_tree_runtime",
    "packages.prompt_harness_runtime",
    "packages.web_search_runtime",
    "pydantic",
    "re",
    "typing",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "apps",
    "packages.adapters",
    "packages.provider_runtime",
    "services",
    "subprocess",
)
REQUIRED_TERMS = (
    "CognitionRuntime",
    "CognitionTurnAssembly",
    "SafeCognitionProjection",
    "assemble_turn",
    "classify_intent",
    "assemble_prompt_harness",
    "assemble_adaptive_prompt_harness",
    "adaptive_context_policy_for_route",
    "decide_compaction",
    "LocalMemoryLoop",
    "write_document_to_obsidian_vault",
    "web_search_required",
    "grounding_required",
    "raw_prompt_persisted: Literal[False]",
    "raw_context_persisted: Literal[False]",
    "raw_payload_persisted: Literal[False]",
)
FORBIDDEN_TOKENS = (
    "subprocess",
    "ProviderRuntimeConfig",
    "create_provider",
    "ProviderWorker",
    "ToolWorker",
    "IntentWorker",
    "Path.write_text",
    "raw_prompt_persisted=True",
    "raw_context_persisted=True",
    "raw_payload_persisted=True",
)
REQUIRED_DOC_PHRASES = (
    "Cognition Runtime",
    "bounded Agentic Turn Loop",
    "grounding is enforced",
)


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file()) if root.exists() else []


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        return None if node.level else node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def main() -> int:
    failures: list[str] = []
    if not COGNITION.is_dir():
        failures.append("packages/cognition_runtime is missing")
    text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(COGNITION))
    for term in REQUIRED_TERMS:
        if term not in text:
            failures.append(f"cognition runtime missing required term: {term}")
    for token in FORBIDDEN_TOKENS:
        if token in text:
            failures.append(f"cognition runtime contains forbidden token: {token}")
    if "Approved memory ref is available." in text:
        failures.append("cognition runtime must not use tombstone memory prompt text")
    if "User requested a simple assistant response." in text:
        failures.append("cognition runtime must not replace real user input with canned simple summaries")
    if "assemble_adaptive_prompt_harness" not in text or "adaptive_context_policy_for_route" not in text:
        failures.append("cognition runtime must use adaptive prompt harness budgets")
    if "User asked:" not in text:
        failures.append("cognition runtime must carry the real user input into prompt context")
    for path in _python_files(COGNITION):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = _module_from_import(node)
            if module is None:
                continue
            if _matches_prefix(module, FORBIDDEN_IMPORT_PREFIXES):
                failures.append(f"{path.relative_to(ROOT).as_posix()} imports forbidden dependency: {module}")
            if not _matches_prefix(module, ALLOWED_IMPORT_PREFIXES):
                failures.append(f"{path.relative_to(ROOT).as_posix()} imports non-approved dependency: {module}")
    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_cognition_runtime_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_cognition_runtime_boundaries.py")
    docs = "\n".join(path.read_text(encoding="utf-8") for path in (VALIDATION_GATES, PROJECT_STATUS) if path.is_file())
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"cognition docs/status missing phrase: {phrase}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS cognition runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
