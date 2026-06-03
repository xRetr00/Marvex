"""Tool-block reason-code surfacing (services.core.main).

A blocked/failed capability puts its reason under
``result.safe_result.reason_code`` (or the error envelope's ``code``). The older
lookups only checked the top level, so every block collapsed to the generic
``tool_execution_blocked``. These tests lock in the corrected extraction and the
human-readable copy.
"""

from __future__ import annotations

from services.core.main import _tool_block_message, _tool_reason_code


def test_reason_code_read_from_safe_result():
    tool_response = {
        "ok": False,
        "result": {"status": "denied", "safe_result": {"reason_code": "file.not_found"}},
    }
    assert _tool_reason_code(tool_response) == "file.not_found"


def test_reason_code_read_from_error_envelope():
    tool_response = {
        "ok": False,
        "error": {"code": "file.sandbox_violation"},
        "result": {"safe_result": {}},
    }
    assert _tool_reason_code(tool_response) == "file.sandbox_violation"


def test_reason_code_falls_back_to_generic_when_absent():
    assert _tool_reason_code({"ok": False, "result": {}}) == "tool_execution_blocked"


def test_block_message_uses_friendly_copy_for_known_code():
    assert _tool_block_message("file.read", "file.not_found") == "I couldn't find that file."


def test_block_message_matches_dynamic_code_by_prefix():
    message = _tool_block_message("playwright_mcp.task", "playwright_mcp_execution_failed:OSError")
    assert "browser" in message.lower()


def test_block_message_includes_reason_for_unknown_code():
    message = _tool_block_message("file.read", "some_unmapped_code")
    assert "some_unmapped_code" in message
