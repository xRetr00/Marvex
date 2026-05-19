from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_completion_surfaces_exist_for_phase_unlock() -> None:
    required = {
        "packages/capability_runtime/selection.py": "select_tools_for_request",
        "packages/provider_selection_runtime/__init__.py": "ProviderSelectionRuntime",
        "packages/assistant_turn_integration/recovery.py": "TurnRecoveryPolicy",
        "packages/connector_runtime/runtime.py": "ConnectorRuntime",
        "packages/learning_runtime/__init__.py": "LearningPipelineRunner",
        "packages/grounded_answer_runtime/__init__.py": "validate_grounded_citations",
    }

    for rel, marker in required.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert marker in text, rel


def test_stale_phase_lock_wording_is_absent_except_blacklist_classification() -> None:
    forbidden = (
        "waiting Phase 3",
        "blocked by governance",
        "broad OAuth blocked",
        "hidden auto-fetch blocked",
        "MCP launch blocked",
        "shell blocked",
        "retry/fallback blocked",
        "semantic memory blocked",
        "auto-write blocked",
        "profile write blocked",
    )
    scanned = []
    for root in ("docs", "packages", "scripts"):
        for path in (ROOT / root).rglob("*"):
            if path.suffix.lower() not in {".py", ".md", ".txt"} or not path.is_file():
                continue
            scanned.append(path.relative_to(ROOT).as_posix())
            text = path.read_text(encoding="utf-8")
            for phrase in forbidden:
                assert phrase not in text, f"{phrase} in {path}"
    assert scanned


def test_future_reports_use_required_runtime_completion_categories() -> None:
    template = (ROOT / "templates" / "AGENT_FINAL_REPORT.md").read_text(encoding="utf-8")
    for phrase in (
        "Real runtime behavior added",
        "Foundation/proof-only behavior added",
        "Missing items found and completed",
        "Policy/mode behavior result",
        "Whether Voice Runtime Foundation can start next",
    ):
        assert phrase in template
