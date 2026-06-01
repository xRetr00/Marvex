from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from packages.adapters.capabilities import browser_use, computer_use, playwright_mcp
from packages.adapters.capabilities.playwright_mcp import PlaywrightMcpServerConfig, execute_playwright_mcp_task


def test_chrome_default_profile_is_first_class_browser_use_candidate(monkeypatch, tmp_path: Path) -> None:
    local_app_data = tmp_path / "LocalAppData"
    default_profile = local_app_data / "Google" / "Chrome" / "User Data" / "Default"
    default_profile.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    assert hasattr(browser_use, "chrome_profile_candidates")
    candidates = browser_use.chrome_profile_candidates(preferred_profile="Default")

    assert candidates[0]["mode"] == "system_chrome"
    assert candidates[0]["profile_directory"] == "Default"
    assert candidates[0]["user_data_dir"] == os.path.join(
        str(local_app_data),
        "Google",
        "Chrome",
        "User Data",
    )


def test_windows_mcp_builtin_server_config_defaults_to_local_stdio() -> None:
    assert hasattr(computer_use, "WindowsMcpServerConfig")
    config = computer_use.WindowsMcpServerConfig.builtin()

    assert config.server_id == "windows-mcp"
    assert config.command == "uvx"
    assert config.args == ("windows-mcp", "serve", "--transport", "stdio")
    assert config.transport == "stdio"
    assert config.local_only is True
    assert "PowerShell" in config.destructive_tools
    assert "Registry" in config.destructive_tools


def test_browser_use_denies_vision_required_when_model_lacks_vision(monkeypatch) -> None:
    from packages.capability_runtime import (
        CapabilityCallProposal,
        CapabilityExecutionMode,
        CapabilityExecutionRequest,
        CapabilityKind,
        CapabilityPermissionDecision,
        CapabilityRef,
        HumanApprovalRequirement,
    )

    class _Spec:
        pass

    monkeypatch.setattr(browser_use.importlib.util, "find_spec", lambda name: _Spec())
    capability_ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser_use.task")
    request = CapabilityExecutionRequest(
        schema_version="1",
        request_id="request-browser-vision",
        trace_id="trace-browser-vision",
        turn_id="turn-browser-vision",
        proposal=CapabilityCallProposal(
            schema_version="1",
            proposal_id="proposal-browser-vision",
            trace_id="trace-browser-vision",
            turn_id="turn-browser-vision",
            capability_ref=capability_ref,
            proposed_action="browser_use_task",
            risk_level="high",
            arguments_schema={"type": "object"},
        ),
        permission_decision=CapabilityPermissionDecision(
            schema_version="1",
            decision_id="decision-browser-vision",
            capability_ref=capability_ref,
            decision="approved",
            reason_code="owner_mode",
            human_approval=HumanApprovalRequirement(
                required=False,
                reason_code="owner_mode",
                prompt_user_visible=False,
            ),
        ),
        arguments={
            "task": "Open YouTube",
            "live_execution_enabled": True,
            "provider_base_url": "http://localhost:20128/v1",
            "automation_vision_required": True,
            "provider_model_supports_vision": False,
        },
        execution_mode=CapabilityExecutionMode.APPROVED_EXECUTE,
    )

    report = browser_use.execute_browser_use_task(request)

    assert report.status == "denied"
    assert report.reason_code == "vision_model_required"


def test_playwright_mcp_builtin_server_config_is_headed_chrome_by_default() -> None:
    config = PlaywrightMcpServerConfig.builtin()

    assert config.server_id == "playwright-mcp"
    assert config.command == "npx"
    assert config.args == ("@playwright/mcp@latest", "--browser=chrome")
    assert config.headed_by_default is True
    assert config.transport == "stdio"


def test_playwright_mcp_extension_mode_uses_extension_arg() -> None:
    config = PlaywrightMcpServerConfig.builtin(extension_mode=True)

    assert config.args == ("@playwright/mcp@latest", "--extension")
    assert config.extension_mode is True


def test_playwright_mcp_unsafe_code_tool_requires_extra_approval(monkeypatch) -> None:
    from packages.capability_runtime import (
        CapabilityCallProposal,
        CapabilityExecutionMode,
        CapabilityExecutionRequest,
        CapabilityKind,
        CapabilityPermissionDecision,
        CapabilityRef,
        HumanApprovalRequirement,
    )

    capability_ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="playwright_mcp.task")
    request = CapabilityExecutionRequest(
        schema_version="1",
        request_id="request-playwright",
        trace_id="trace-playwright",
        turn_id="turn-playwright",
        proposal=CapabilityCallProposal(
            schema_version="1",
            proposal_id="proposal-playwright",
            trace_id="trace-playwright",
            turn_id="turn-playwright",
            capability_ref=capability_ref,
            proposed_action="playwright_mcp_task",
            risk_level="high",
            arguments_schema={"type": "object"},
        ),
        permission_decision=CapabilityPermissionDecision(
            schema_version="1",
            decision_id="decision-playwright",
            capability_ref=capability_ref,
            decision="approved",
            reason_code="owner_mode",
            human_approval=HumanApprovalRequirement(
                required=False,
                reason_code="owner_mode",
                prompt_user_visible=False,
            ),
        ),
        arguments={
            "live_execution_enabled": True,
            "tool_name": "browser_evaluate",
        },
        execution_mode=CapabilityExecutionMode.APPROVED_EXECUTE,
    )

    report = execute_playwright_mcp_task(request)

    assert report.status == "denied"
    assert report.reason_code == "playwright_mcp_unsafe_code_requires_approval"


def test_computer_use_missing_dependency_safe_result_points_to_runtime_install() -> None:
    report = computer_use.ComputerUseExecutionReport(
        status="denied",
        reason_code="computer_use_dependency_unavailable",
        install_dep_id="computer_use",
        missing_dependencies=("mcp", "uiautomation"),
    )
    request = SimpleNamespace(
        arguments={},
        trace_id="trace-computer-missing",
        turn_id="turn-computer-missing",
        approval_decision=object(),
        proposal=SimpleNamespace(
            capability_ref=SimpleNamespace(identifier="computer_use.action"),
        ),
    )

    safe, raw_persisted = computer_use.computer_use_safe_result(request=request, report=report)

    assert safe["install_dep_id"] == "computer_use"
    assert safe["missing_dependencies"] == ("mcp", "uiautomation")
    assert raw_persisted is False


def test_playwright_mcp_missing_dependency_safe_result_points_to_runtime_install() -> None:
    report = playwright_mcp.PlaywrightMcpExecutionReport(
        status="denied",
        reason_code="playwright_mcp_dependency_unavailable",
        install_dep_id="mcp",
        missing_dependencies=("mcp",),
    )
    request = SimpleNamespace(
        arguments={},
        trace_id="trace-playwright-missing",
        turn_id="turn-playwright-missing",
        proposal=SimpleNamespace(
            capability_ref=SimpleNamespace(identifier="playwright_mcp.task"),
        ),
    )

    safe, raw_persisted = playwright_mcp.playwright_mcp_safe_result(request=request, report=report)

    assert safe["install_dep_id"] == "mcp"
    assert safe["missing_dependencies"] == ("mcp",)
    assert raw_persisted is False
