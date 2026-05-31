from __future__ import annotations

import json

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


def test_approved_browser_use_task_executes_backend_and_persists_raw_artifacts(monkeypatch, tmp_path) -> None:
    import services.tool_worker.controller as controller

    def fake_browser_backend(request):
        from packages.adapters.capabilities.browser_use import BrowserUseExecutionReport

        return BrowserUseExecutionReport(
            status="succeeded",
            backend="browser-use",
            profile_mode="system_chrome",
            profile_directory="Default",
            step_count=2,
            action_count=3,
            final_url="https://www.youtube.com/",
            final_title="YouTube",
            artifact_payloads={
                "dom": "<html><title>YouTube</title></html>",
                "screenshot": "base64-screen",
                "keystrokes": [{"action": "type", "text": "youtube"}],
                "history": {"done": True},
            },
        )

    monkeypatch.setattr(controller, "execute_browser_use_task", fake_browser_backend)
    monkeypatch.setenv("MARVEX_AUTOMATION_ARTIFACT_DIR", str(tmp_path))

    result = ToolWorkerController().execute(
        trace_id="trace-browser-live",
        turn_id="turn-browser-live",
        capability_id="browser_use.task",
        action="open youtube",
        capability="browser_click_type",
        resource_type="browser",
        arguments={
            "task": "open youtube",
            "approval_request_id": "approval-turn-browser-live",
            "approval_decision": "approve",
            "raw_persistence_enabled": True,
        },
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result.status == "succeeded"
    safe = result.result.safe_result
    assert safe["live_execution"] is True
    assert safe["profile_mode"] == "system_chrome"
    assert safe["profile_directory"] == "Default"
    assert safe["final_url_host"] == "www.youtube.com"
    assert safe["raw_dom_persisted"] is True
    assert safe["raw_screenshot_persisted"] is True
    assert safe["raw_keystrokes_persisted"] is True
    assert result.result.raw_output_persisted is True
    artifact_ids = safe["artifact_ids"]
    assert set(artifact_ids) == {"dom", "screenshot", "keystrokes", "history"}
    persisted = list(tmp_path.glob("*.json"))
    assert len(persisted) == 4
    assert any(json.loads(path.read_text(encoding="utf-8"))["artifact_kind"] == "dom" for path in persisted)


def test_approved_windows_computer_use_calls_windows_mcp_backend(monkeypatch, tmp_path) -> None:
    import services.tool_worker.controller as controller

    def fake_windows_backend(request):
        from packages.adapters.capabilities.computer_use import ComputerUseExecutionReport

        return ComputerUseExecutionReport(
            status="succeeded",
            backend="windows-mcp",
            tool_name="Click",
            action_count=1,
            artifact_payloads={
                "screen": "base64-desktop",
                "action_log": [{"tool": "Click", "x": 25, "y": 50}],
            },
        )

    monkeypatch.setattr(controller, "execute_windows_computer_action", fake_windows_backend)
    monkeypatch.setenv("MARVEX_AUTOMATION_ARTIFACT_DIR", str(tmp_path))

    result = ToolWorkerController().execute(
        trace_id="trace-computer-live",
        turn_id="turn-computer-live",
        capability_id="computer_use.action",
        action="click on the desktop",
        capability="computer_actions",
        resource_type="desktop",
        arguments={
            "action_kind": "click",
            "x": 25,
            "y": 50,
            "approval_request_id": "approval-turn-computer-live",
            "approval_decision": "approve",
            "raw_persistence_enabled": True,
        },
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result.status == "succeeded"
    safe = result.result.safe_result
    assert safe["live_execution"] is True
    assert safe["adapter"] == "windows-desktop-computer-use"
    assert safe["backend"] == "windows-mcp"
    assert safe["tool_name"] == "Click"
    assert safe["raw_screen_persisted"] is True
    assert safe["raw_action_payload_persisted"] is True
    assert result.result.raw_output_persisted is True


def test_destructive_computer_actions_still_require_explicit_action_approval() -> None:
    result = ToolWorkerController().execute(
        trace_id="trace-computer-destroy",
        turn_id="turn-computer-destroy",
        capability_id="computer_use.action",
        action="shutdown this computer",
        capability="computer_actions",
        resource_type="desktop",
        arguments={
            "action_kind": "shutdown",
            "approval_request_id": "approval-turn-computer-destroy",
            "approval_decision": "approve",
        },
    )

    assert result.ok is False
    assert result.blocked is True
    assert result.result is not None
    assert result.result.status == "requires_human_approval"
    assert result.error is not None
    assert result.error.code == "destructive_action_approval_required"
