from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_current_autonomy_docs_do_not_classify_normal_capabilities_as_blanket_blocked() -> None:
    checked = {
        "PROJECT_STATUS.md": (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8"),
        "docs/VALIDATION_GATES.md": (ROOT / "docs" / "VALIDATION_GATES.md").read_text(encoding="utf-8"),
    }
    blanket_block_phrases = (
        "broad OAuth sync",
        "hidden auto-fetch",
        "retry/fallback policy",
        "arbitrary MCP install/execute",
        "arbitrary tool execution without approval",
        "silent policy/skill mutation",
    )

    for path, text in checked.items():
        for line in text.splitlines():
            normalized = line.strip().lower()
            if not normalized.startswith("blocked:") and not normalized.startswith("still blocked"):
                continue
            for phrase in blanket_block_phrases:
                assert phrase.lower() not in normalized, f"{path} keeps blanket blocked language for {phrase!r}: {line}"
