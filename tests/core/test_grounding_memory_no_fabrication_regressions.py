from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from packages.contracts import AssistantTurnResult


ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_NON_TEST_LITERALS = (
    "Grounded answer uses available evidence ",
    "example.test/web.evidence.1",
)


def _run_core_turn(
    text: str,
    *,
    trace_id: str,
    turn_id: str,
    session_id: str | None = None,
    extra: list[str] | None = None,
) -> AssistantTurnResult:
    cmd = [
        sys.executable,
        "-m",
        "services.core.main",
        "--turn-once",
        text,
        "--provider",
        "provider_worker",
        "--worker-provider",
        "fake",
        "--model",
        "fake-model",
        "--trace-id",
        trace_id,
        "--turn-id",
        turn_id,
    ]
    if session_id is not None:
        cmd.extend(["--session-id", session_id])
    cmd.extend(extra or [])
    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    return AssistantTurnResult.model_validate(json.loads(completed.stdout))


def test_non_test_source_must_not_contain_fake_grounded_templates_or_fake_stub_urls() -> None:
    offenders: list[str] = []
    for path in (ROOT / "packages").rglob("*.py"):
        if "tests" in path.parts:
            continue
        content = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_NON_TEST_LITERALS:
            if forbidden in content:
                offenders.append(f"{path.relative_to(ROOT)} -> {forbidden}")
    for path in (ROOT / "services").rglob("*.py"):
        if "tests" in path.parts:
            continue
        content = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_NON_TEST_LITERALS:
            if forbidden in content:
                offenders.append(f"{path.relative_to(ROOT)} -> {forbidden}")

    assert offenders == []


def test_grounded_route_with_real_evidence_must_invoke_provider_and_validate_real_citations() -> None:
    result = _run_core_turn(
        "Give a grounded answer with current web evidence about browser-use.",
        trace_id="trace-core-grounded-provider-regression",
        turn_id="turn-core-grounded-provider-regression",
        extra=["--web-search", "fake"],
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.provider_turn_refs != []
    assert "[web.evidence.1]" in result.assistant_final_response.text
    assert result.metadata["grounding"]["citation_validation"] == "citation.validated"


def test_grounded_route_with_no_evidence_must_not_emit_fabricated_citations_or_fake_evidence() -> None:
    result = _run_core_turn(
        "Give a grounded answer about a private unreleased fact.",
        trace_id="trace-core-grounded-no-evidence-regression",
        turn_id="turn-core-grounded-no-evidence-regression",
        extra=["--web-search", "none"],
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "web.evidence." not in result.assistant_final_response.text
    assert "example.test" not in result.assistant_final_response.text
    assert result.metadata["grounding"]["citation_validation"] == "citation.evidence_missing"
    assert result.metadata["grounding"]["fabricated"] is False


def test_memory_route_with_recalled_approved_memory_must_invoke_provider_with_memory_in_prompt(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory-vault"
    session_id = "session-memory-provider-regression"
    _run_core_turn(
        "Remember that my preferred project codename is Cedar.",
        trace_id="trace-core-memory-write-regression",
        turn_id="turn-core-memory-write-regression",
        session_id=session_id,
        extra=["--memory-vault-root", str(memory_root)],
    )

    result = _run_core_turn(
        "What project codename do I prefer?",
        trace_id="trace-core-memory-read-regression",
        turn_id="turn-core-memory-read-regression",
        session_id=session_id,
        extra=["--memory-vault-root", str(memory_root), "--web-search", "none"],
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.provider_turn_refs != []
    assert result.metadata["prompt_fidelity"]["memory_content_present"] is True
