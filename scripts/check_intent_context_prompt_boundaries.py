from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTENT_RUNTIME = ROOT / "packages" / "intent_runtime"
CONTEXT_RUNTIME = ROOT / "packages" / "context_runtime"
PROMPT_HARNESS = ROOT / "packages" / "prompt_harness_runtime"
HARNESS_ADAPTERS = ROOT / "packages" / "adapters" / "prompt_harness"
INTENT_ADAPTERS = ROOT / "packages" / "adapters" / "intent"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

NON_OWNER_ROOTS = (
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "telemetry",
    ROOT / "packages" / "memory_runtime",
    ROOT / "packages" / "session_runtime",
    ROOT / "packages" / "control_plane_api",
)
FORBIDDEN_NON_OWNER_IMPORTS = (
    "packages.intent_runtime",
    "packages.context_runtime",
    "packages.prompt_harness_runtime",
    "packages.adapters.prompt_harness",
)
REQUIRED_INTENT_TERMS = (
    "IntentRef",
    "IntentCandidate",
    "IntentClassificationRequest",
    "IntentClassificationResult",
    "IntentConfidence",
    "IntentRouteDecision",
    "IntentRiskSignal",
    "IntentAmbiguitySignal",
    "ClarificationNeededDecision",
    "SafeIntentProjection",
)
REQUIRED_CONTEXT_TERMS = (
    "ContextSourceRef",
    "ContextCandidate",
    "ContextEligibilityDecision",
    "ContextPack",
    "ContextBudget",
    "ContextDeliveryPolicy",
    "ContextExclusionReason",
    "SafeContextProjection",
    "all_tools_allowed: Literal[False]",
    "raw_transcripts_allowed: Literal[False]",
)
REQUIRED_PROMPT_TERMS = (
    "PromptSection",
    "PromptHarnessPlan",
    "PromptAssemblyRequest",
    "PromptAssemblyResult",
    "PromptBudgetReport",
    "SafePromptProjection",
    "CompactionCandidate",
    "CompactionDecision",
    "ToolResultClearingDecision",
    "MemoryOffloadDecision",
    "PlanningNeedDecision",
    "TaskDecompositionHint",
    "VerificationNeedDecision",
    "HarnessTelemetrySummary",
)
REQUIRED_ADAPTER_TERMS = (
    "SemanticRouterHarnessAdapter",
    "SemanticRouterThresholdPolicy",
    "DisabledSemanticRouterBackend",
    "PromptHarnessGuardrailsAdapter",
    "DisabledGuardrailsBackend",
    "HarnessExternalBackend",
    "DisabledHarnessLibraryBackend",
)
FORBIDDEN_TEXT = (
    "raw_prompt_persisted=True",
    "raw_context_persisted=True",
    "raw_transcript_persisted=True",
    "all_tools_allowed: Literal[True]",
    "all_memory_allowed: Literal[True]",
    "autonomous_loop_allowed: Literal[True]",
    "automatic_retry_allowed: Literal[True]",
    "execute_request(",
    "dispatch(",
)
REQUIRED_DOC_PHRASES = (
    "Intent, Context, and Prompt Harness Foundation",
    "IntentRuntime exists",
    "ContextRuntime/PromptHarness",
    "no all-tools dumping",
    "CapabilityRuntime remains authoritative",
)


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


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


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _require_terms(label: str, text: str, terms: tuple[str, ...], failures: list[str]) -> None:
    for term in terms:
        if term not in text:
            failures.append(f"{label} missing required term: {term}")


def _scan_non_owner_imports(failures: list[str]) -> None:
    for root in NON_OWNER_ROOTS:
        for path in _python_files(root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = _module_from_import(node)
                if module and _matches_prefix(module, FORBIDDEN_NON_OWNER_IMPORTS):
                    failures.append(f"{_rel(path)} imports prompt harness owner boundary: {module}")


def main() -> int:
    failures: list[str] = []
    for root, label in (
        (INTENT_RUNTIME, "IntentRuntime"),
        (CONTEXT_RUNTIME, "ContextRuntime"),
        (PROMPT_HARNESS, "PromptHarnessRuntime"),
        (HARNESS_ADAPTERS, "PromptHarnessAdapters"),
    ):
        if not root.is_dir():
            failures.append(f"missing {root.relative_to(ROOT).as_posix()}")

    intent_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(INTENT_RUNTIME))
    context_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(CONTEXT_RUNTIME))
    prompt_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(PROMPT_HARNESS))
    adapter_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(HARNESS_ADAPTERS) + _python_files(INTENT_ADAPTERS))

    _require_terms("IntentRuntime", intent_text, REQUIRED_INTENT_TERMS, failures)
    _require_terms("ContextRuntime", context_text, REQUIRED_CONTEXT_TERMS, failures)
    _require_terms("PromptHarnessRuntime", prompt_text, REQUIRED_PROMPT_TERMS, failures)
    _require_terms("Harness adapters", adapter_text, REQUIRED_ADAPTER_TERMS, failures)

    combined_text = "\n".join((intent_text, context_text, prompt_text, adapter_text))
    for token in FORBIDDEN_TEXT:
        if token in combined_text:
            failures.append(f"prompt harness foundation contains forbidden token: {token}")

    _scan_non_owner_imports(failures)

    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_intent_context_prompt_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_intent_context_prompt_boundaries.py")

    docs = "\n".join(path.read_text(encoding="utf-8") for path in (VALIDATION_GATES, PROJECT_STATUS) if path.is_file())
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"intent/context/prompt docs/status missing phrase: {phrase}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS intent context prompt boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
