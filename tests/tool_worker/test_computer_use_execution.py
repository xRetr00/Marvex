from __future__ import annotations

from services.tool_worker.controller import ToolWorkerController


def test_browser_use_task_requires_approval_before_execution() -> None:
    result = ToolWorkerController().execute(
        trace_id="trace-browser",
        turn_id="turn-browser",
        capability_id="browser_use.task",
        action="open a browser page",
        capability="browser_click_type",
        resource_type="browser",
        arguments={"task": "open example.com"},
    )

    assert result.ok is False
    assert result.blocked is True
    assert result.result is not None
    assert result.result.status == "requires_human_approval"
    assert result.result.raw_input_persisted is False
    assert result.result.raw_output_persisted is False


def test_approved_browser_use_task_uses_controlled_adapter_without_raw_payloads() -> None:
    result = ToolWorkerController().execute(
        trace_id="trace-browser",
        turn_id="turn-browser",
        capability_id="browser_use.task",
        action="read browser page title",
        capability="browser_click_type",
        resource_type="browser",
        arguments={
            "task": "read the current page title",
            "approval_request_id": "approval-turn-browser",
            "approval_decision": "approve",
        },
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result.status in {"succeeded", "denied"}
    assert result.result.safe_result["adapter"] == "browser-use"
    assert result.result.safe_result["approval_required"] is True
    assert result.result.raw_input_persisted is False
    assert result.result.raw_output_persisted is False


def test_approved_desktop_computer_action_uses_policy_gated_adapter() -> None:
    result = ToolWorkerController().execute(
        trace_id="trace-computer",
        turn_id="turn-computer",
        capability_id="computer_use.action",
        action="inspect focused control",
        capability="computer_actions",
        resource_type="desktop",
        arguments={
            "action_kind": "inspect",
            "approval_request_id": "approval-turn-computer",
            "approval_decision": "approve",
        },
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result.safe_result["adapter"] == "windows-desktop-computer-use"
    assert result.result.safe_result["ufo_external_process"] == "operator_configured"
    assert result.result.safe_result["omniparser_external_process"] == "operator_configured"
    assert result.result.safe_result["raw_screen_persisted"] is False
