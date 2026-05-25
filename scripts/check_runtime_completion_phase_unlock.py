import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_MARKERS = {
    "packages/grounded_answer_runtime/__init__.py": (
        "validate_grounded_citations",
        "web_search_bundle_to_context_candidate",
    ),
    "packages/prompt_harness_runtime/models.py": (
        "_route_profile",
        "evidence_token_budget",
        "memory_token_budget",
        "tool_schema_token_budget",
        "Use citation markers exactly as supplied",
    ),
    "packages/intent_runtime/hybrid.py": (
        "IntentPlan",
        "secondary_intents",
        "clarification_stop",
        "GROUNDED_ANSWER",
    ),
    "packages/capability_runtime/selection.py": (
        "select_tools_for_request",
        "provider_tool_schemas",
        "approval_requirement",
        "mcp_allowlist",
    ),
    "packages/capability_runtime/autonomy.py": (
        "hard_block_blacklist_only",
        "shell_command_execution",
        "file_delete",
        "provider_retry_fallback",
    ),
    "packages/provider_selection_runtime/__init__.py": (
        "ProviderSelectionRuntime",
        "ProviderCandidate",
        "ProviderSelectionRequest",
        "ProviderFallbackPolicy",
        "ProviderRetryPolicy",
        "ModelCapabilityRequirement",
        "SafeProviderSelectionProjection",
    ),
    "packages/assistant_turn_integration/recovery.py": (
        "TurnRecoveryPolicy",
        "ProviderFailureRecovery",
        "ToolFailureRecovery",
        "WebSearchFallback",
        "MemoryRetrievalFallback",
        "ClarificationFallback",
        "SafeFailureProjection",
    ),
    "packages/learning_runtime/__init__.py": (
        "FeedbackEvent",
        "LearningPipelineRunner",
        "LearningCandidateStore",
        "apply_candidate",
        "MemoryHotnessUpdate",
        "RouteExampleCandidate",
    ),
    "packages/connector_runtime/runtime.py": (
        "ConnectorRuntime",
        "ConnectorSyncRunResult",
        "run_autofetch",
        "canonicalize_source_document",
        "MemoryTreeRuntime",
    ),
    "packages/control_plane_api/runtime.py": (
        "{CONTROL_PREFIX}/feedback",
        "{CONTROL_PREFIX}/learning/candidates",
        "learning_runner",
        "runtime-policy",
    ),
    "apps/control_plane_web/src/App.tsx": (
        "Feedback / Learning",
        "Runtime Policy",
        "Auto-Fetch",
    ),
    "templates/AGENT_FINAL_REPORT.md": (
        "Real runtime behavior added",
        "Foundation/proof-only behavior added",
        "Policy/mode behavior result",
        "Whether Voice Runtime Foundation can start next",
    ),
}

STALE_PHASE_LOCK_PATTERNS = (
    ("phase_waiting_lock", re.compile(r"waiting\s+Phase\s+3")),
    ("governance_blanket_block", re.compile(r"blocked\s+by\s+governance")),
    ("oauth_blanket_block", re.compile(r"broad\s+OAuth\s+blocked")),
    ("autofetch_blanket_block", re.compile(r"hidden\s+auto-fetch\s+blocked")),
    ("mcp_launch_blanket_block", re.compile(r"MCP\s+launch\s+blocked")),
    ("shell_blanket_block", re.compile(r"shell\s+blocked")),
    ("retry_fallback_blanket_block", re.compile(r"retry/fallback\s+blocked")),
    ("semantic_memory_blanket_block", re.compile(r"semantic\s+memory\s+blocked")),
    ("auto_write_blanket_block", re.compile(r"auto-write\s+blocked")),
    ("profile_write_blanket_block", re.compile(r"profile\s+write\s+blocked")),
)


def main() -> int:
    failures: list[str] = []
    for rel_path, markers in REQUIRED_MARKERS.items():
        path = ROOT / rel_path
        if not path.exists():
            failures.append(f"missing required runtime completion artifact: {rel_path}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                failures.append(f"{rel_path} missing marker: {marker}")

    for root in ("docs", "packages", "scripts", "templates"):
        for path in (ROOT / root).rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8")
            for label, pattern in STALE_PHASE_LOCK_PATTERNS:
                if pattern.search(text):
                    failures.append(f"stale phase-lock wording in {path.relative_to(ROOT).as_posix()}: {label}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS runtime completion phase unlock gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
