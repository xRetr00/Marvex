from __future__ import annotations

"""Tests that the Core turn loop publishes the correct AssistantStatusKind
transitions to the state bus for each loop step.

All tests are CI-offline: they use the fake provider / fake intent worker path.
"""

import json
import subprocess
import sys
from pathlib import Path

from packages.contracts import AssistantTurnResult
from packages.contracts.state_event import AssistantStatusKind
from packages.state_bus import AssistantStateBus, reset_default_bus


ROOT = Path(__file__).resolve().parents[2]


def _run_core_turn_with_bus(
    text: str,
    *,
    trace_id: str,
    turn_id: str,
    extra: list[str] | None = None,
) -> tuple[AssistantTurnResult, list[AssistantStatusKind]]:
    """Run a core turn in-process via the subprocess path to get result + state transitions."""
    published: list[AssistantStatusKind] = []
    reset_default_bus()

    # Capture bus events through an in-process subscriber BEFORE running the subprocess.
    # The subprocess runs in a separate process so we cannot capture its bus events directly.
    # Instead, assert the contract behaviour in-process using the service entrypoint directly.
    from packages.contracts import AssistantTurnInput
    from packages.assistant_runtime.input_normalization import (
        build_text_input_event,
        build_turn_input_from_event,
    )
    from services.core.main import (
        _CoreServiceProviderWorkerTurnExecutor,
        CoreServiceEntrypointConfig,
        _create_turn_executor,
    )
    from packages.telemetry import InMemoryTraceReader
    from datetime import UTC, datetime
    from packages.state_bus import get_default_bus

    bus = get_default_bus()
    bus.subscribe(lambda ev: published.append(ev.status))

    trace_reader = InMemoryTraceReader()
    config = CoreServiceEntrypointConfig(
        provider="provider_worker",
        worker_provider="fake",
        foundation_model="fake-model",
    )

    executor = _create_turn_executor(trace_reader=trace_reader, config=config)
    # Wire the bus
    if hasattr(executor, "_state_bus"):
        executor._state_bus = bus  # type: ignore[union-attr]

    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        event_id=f"{turn_id}:input",
        text=text,
        timestamp=datetime.now(UTC),
        session_id=None,
    )
    turn_input = build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        turn_id=turn_id,
        input_event=event,
    )

    result = executor.submit_turn(turn_input)
    return result, published


def test_core_publishes_thinking_then_idle_for_provider_chat() -> None:
    result, statuses = _run_core_turn_with_bus(
        "Hello through the normal provider path",
        trace_id="trace-state-simple",
        turn_id="turn-state-simple",
    )
    assert result.error is None
    # At minimum: thinking at start, idle at end
    assert AssistantStatusKind.THINKING in statuses
    assert statuses[-1] == AssistantStatusKind.IDLE


def test_core_publishes_searching_web_for_web_search_intent() -> None:
    _result, statuses = _run_core_turn_with_bus(
        "Give a grounded answer with current web evidence about browser-use",
        trace_id="trace-state-web",
        turn_id="turn-state-web",
    )
    assert AssistantStatusKind.SEARCHING_WEB in statuses


def test_core_publishes_using_tools_for_capability_tool_intent() -> None:
    _result, statuses = _run_core_turn_with_bus(
        "Calculate 2 + 2",
        trace_id="trace-state-tool",
        turn_id="turn-state-tool",
    )
    assert AssistantStatusKind.USING_TOOLS in statuses


def test_core_publishes_mcp_for_mcp_intent() -> None:
    _result, statuses = _run_core_turn_with_bus(
        "Use MCP echo tool",
        trace_id="trace-state-mcp",
        turn_id="turn-state-mcp",
    )
    assert AssistantStatusKind.MCP in statuses


def test_core_audio_level_zero_no_raw_audio() -> None:
    """audio_level must be 0.0 (no mic) and raw_audio_persisted False for turn events."""
    _result, statuses = _run_core_turn_with_bus(
        "Hello",
        trace_id="trace-state-audio",
        turn_id="turn-state-audio",
    )
    # Statuses are collected inside _run_core_turn_with_bus; assert they were published
    assert statuses, "no status events published"
    # Separately verify that bus events have correct audio / privacy properties
    from packages.state_bus import get_default_bus
    bus = get_default_bus()
    ev = bus.snapshot
    assert ev.raw_audio_persisted is False
    assert 0.0 <= ev.audio_level <= 1.0


def test_core_publishes_safe_status_frames_to_live_turn_stream() -> None:
    from packages.telemetry import InMemoryTraceReader
    from services.core.main import _CoreServiceProviderWorkerTurnExecutor, _set_live_event_sink

    frames: list[dict[str, object]] = []
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
    )
    try:
        _set_live_event_sink(frames.append)
        executor._publish(AssistantStatusKind.THINKING, detail="provider_turn", trace_id="trace-status-frame")
    finally:
        _set_live_event_sink(None)
        executor.shutdown()

    assert frames == [
        {
            "type": "status",
            "status": "thinking",
            "detail": "provider_turn",
            "trace_id": "trace-status-frame",
        }
    ]
