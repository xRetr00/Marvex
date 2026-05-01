from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSISTANT_TURN_SPINE = ROOT / "docs" / "ASSISTANT_TURN_SPINE.md"
AI_AGENT_RULES = ROOT / "docs" / "AI_AGENT_RULES.md"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
TASK_SPEC_TEMPLATE = ROOT / "templates" / "TASK_SPEC.md"

ASSISTANT_MODULE_TERMS = [
    "tool execution",
    "tools",
    "memory",
    "voice",
    "desktop",
    "proactive",
    "ui",
    "http",
    "ipc",
    "service runtime",
    "telemetry persistence",
    "persistent telemetry",
]

REQUIRED_SPINE_PHRASES = [
    "provider turn is not the assistant turn",
    "foundation/test path",
    "Assistant Turn Spine",
    "Future Task Gate",
    "Required Contract Families Before Implementation",
    "Library Research Zones",
]

REQUIRED_GATE_PHRASES = [
    "Assistant Turn Spine",
    "provider turn into assistant turn",
    "contract owns its input",
    "runtime owns dispatch",
    "maintained library",
    "TurnOrchestrator",
    "ProviderRuntime",
]


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def _has_assistant_module_term(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ASSISTANT_MODULE_TERMS)


def _mentions_spine_gate(text: str) -> bool:
    lowered = text.lower()
    return "assistant turn spine" in lowered and "contract" in lowered


def _task_spec_candidates() -> list[Path]:
    candidates = [TASK_SPEC_TEMPLATE]
    for root in [ROOT / "docs", ROOT / "templates"]:
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            if path in candidates:
                continue
            name = path.name.lower()
            if "task_spec" in name or name == "task_spec.md":
                candidates.append(path)
    return candidates


def main() -> int:
    failures: list[str] = []

    spine = _read(ASSISTANT_TURN_SPINE, failures)
    ai_agent_rules = _read(AI_AGENT_RULES, failures)
    validation_gates = _read(VALIDATION_GATES, failures)
    task_spec_template = _read(TASK_SPEC_TEMPLATE, failures)

    spine_lower = spine.lower()
    for phrase in REQUIRED_SPINE_PHRASES:
        if phrase.lower() not in spine_lower:
            failures.append(f"docs/ASSISTANT_TURN_SPINE.md missing phrase: {phrase}")

    if "assistant turn spine" not in ai_agent_rules.lower():
        failures.append("docs/AI_AGENT_RULES.md must reference Assistant Turn Spine")

    validation_lower = validation_gates.lower()
    if "assistant turn spine gate" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must document Assistant Turn Spine Gate")
    if "provider turn is not the assistant turn" not in validation_lower:
        failures.append(
            "docs/VALIDATION_GATES.md must state provider turn is not the assistant turn"
        )

    template_lower = task_spec_template.lower()
    for phrase in REQUIRED_GATE_PHRASES:
        if phrase.lower() not in template_lower:
            failures.append(f"templates/TASK_SPEC.md missing Assistant Turn Spine gate phrase: {phrase}")

    for path in _task_spec_candidates():
        text = path.read_text(encoding="utf-8")
        if _has_assistant_module_term(text) and not _mentions_spine_gate(text):
            failures.append(
                f"{path.relative_to(ROOT).as_posix()} mentions assistant-level modules "
                "without Assistant Turn Spine contract gate"
            )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS assistant turn spine gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
