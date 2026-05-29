"""Tests for the provider tool-catalog grounding (B2 interim fix)."""

from packages.core.orchestration.tool_grounding import (
    available_tools_grounding,
    with_tool_grounding,
)


def test_grounding_lists_real_tools():
    grounding = available_tools_grounding()
    # Built-ins and file tools, sourced from the live registries.
    assert "builtin.calculator" in grounding
    assert "file.read" in grounding
    assert "file.write" in grounding
    assert "file.patch" in grounding


def test_grounding_forbids_invented_capabilities():
    grounding = available_tools_grounding().lower()
    assert "subagent" in grounding
    assert "rag" in grounding
    # The instruction must tell the model not to claim unavailable capabilities.
    assert "never claim" in grounding


def test_with_tool_grounding_appends_to_existing_instructions():
    combined = with_tool_grounding("Follow the house style.")
    assert combined.startswith("Follow the house style.")
    assert "ONLY tools" in combined


def test_with_tool_grounding_handles_none_and_blank():
    assert "ONLY tools" in with_tool_grounding(None)
    assert "ONLY tools" in with_tool_grounding("   ")


def test_grounding_does_not_invent_tools_itself():
    # The grounding must not mention capabilities the system lacks as if real.
    grounding = available_tools_grounding()
    # These appear only in the prohibition sentence, never as bullet entries.
    for forbidden in ("deep_search", "browser browsing tool", "rag pipeline tool"):
        assert f"- {forbidden}" not in grounding
