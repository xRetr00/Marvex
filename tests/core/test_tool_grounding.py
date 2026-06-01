"""Tests for the provider tool-catalog + temporal grounding (B2 + item 05)."""

from datetime import UTC, datetime

from packages.core.orchestration.tool_grounding import (
    available_tools_grounding,
    with_tool_grounding,
)


def test_grounding_lists_real_tools_including_web_search():
    grounding = available_tools_grounding()
    assert "builtin.calculator" in grounding
    assert "file.read" in grounding
    assert "file.write" in grounding
    assert "file.patch" in grounding
    # web.search is advertised even though it lives on the executor.
    assert "web.search" in grounding
    assert "memory.search" in grounding
    assert "memory.remember" in grounding


def test_grounding_injects_current_date():
    grounding = available_tools_grounding(now=datetime(2026, 5, 29, 14, 30, tzinfo=UTC))
    assert "2026-05-29" in grounding
    assert "14:30" in grounding


def test_grounding_steers_to_web_search_for_time_sensitive():
    grounding = available_tools_grounding().lower()
    assert "training cutoff" in grounding
    # Must tell the model to search instead of answering "latest" from memory.
    assert "web.search" in grounding
    assert "latest" in grounding
    assert "from memory" in grounding


def test_grounding_forbids_invented_capabilities():
    grounding = available_tools_grounding().lower()
    assert "subagent" in grounding
    assert "never claim" in grounding


def test_with_tool_grounding_appends_to_existing_instructions():
    combined = with_tool_grounding("Follow the house style.", now=datetime(2026, 5, 29, tzinfo=UTC))
    assert combined.startswith("Follow the house style.")
    assert "ONLY tools" in combined
    assert "2026-05-29" in combined


def test_with_tool_grounding_handles_none_and_blank():
    assert "ONLY tools" in with_tool_grounding(None)
    assert "ONLY tools" in with_tool_grounding("   ")


def test_grounding_does_not_list_phantom_tools():
    grounding = available_tools_grounding()
    for forbidden in ("- agent.deep_search", "- rag", "- browser"):
        assert forbidden not in grounding.lower()
