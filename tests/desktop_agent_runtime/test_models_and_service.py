from __future__ import annotations

import json

from packages.desktop_agent_runtime.models import DesktopContentItem, DesktopPerceptionSnapshot
from services.desktop_agent.controller import DesktopAgentController
from services.desktop_agent.main import handle_jsonl_command


def test_desktop_projection_redacts_and_bounds_content() -> None:
    snapshot = DesktopPerceptionSnapshot.from_items(
        trace_id="trace-desktop",
        snapshot_id="snapshot-1",
        items=(
            DesktopContentItem.from_text(
                source_kind="focused_window",
                text="token=must-not-leak " + ("visible " * 120),
                application="Code",
            ),
        ),
        content_budget_chars=80,
    )

    projection = snapshot.safe_projection()

    assert projection["raw_screen_persisted"] is False
    assert projection["raw_keystrokes_persisted"] is False
    assert "must-not-leak" not in json.dumps(projection)
    assert "[REDACTED]" in snapshot.context_text()
    assert len(snapshot.context_text()) <= 120


def test_desktop_agent_perceive_command_uses_safe_adapter_projection() -> None:
    class Adapter:
        def focused_content(self, *, trace_id: str, content_budget_chars: int) -> DesktopPerceptionSnapshot:
            assert trace_id == "trace-jsonl"
            assert content_budget_chars == 120
            return DesktopPerceptionSnapshot.from_items(
                trace_id=trace_id,
                snapshot_id="snapshot-jsonl",
                items=(DesktopContentItem.from_text(source_kind="focused_window", text="safe terminal output"),),
                content_budget_chars=content_budget_chars,
            )

    controller = DesktopAgentController(perception_adapter=Adapter())
    result = handle_jsonl_command(
        controller,
        json.dumps({"command": "perceive", "trace_id": "trace-jsonl", "content_budget_chars": 120}),
    )

    assert result.ok is True
    assert result.snapshot is not None
    assert result.snapshot.context_text() == "safe terminal output"
    assert result.metadata["local_only"] is True
    assert result.metadata["raw_screen_persisted"] is False
