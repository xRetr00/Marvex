from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.automation_runtime import persist_automation_artifacts
from packages.capability_runtime import (
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


class BrowserUseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BrowserUseAdapterConfig(BrowserUseModel):
    schema_version: str = Field(..., min_length=1)
    adapter_id: str = Field(..., min_length=1)
    backend_name: Literal["browser-use"] = "browser-use"
    backend_enabled: bool = True
    blocked_reason: str = Field(..., min_length=1)
    raw_browser_payload_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "backend_name": self.backend_name,
            "backend_enabled": self.backend_enabled,
            "blocked_reason": self.blocked_reason,
            "raw_browser_payload_persisted": False,
        }


class BrowserUseBackendProbe(BrowserUseModel):
    backend_name: Literal["browser-use"] = "browser-use"
    package_importable: bool
    sdk_package_importable: bool
    execution_supported_without_approval: Literal[False] = False
    playwright_remains_low_level_backend: Literal[True] = True
    blocked_reason: str = Field(..., min_length=1)

    @classmethod
    def from_installed_backend(cls) -> "BrowserUseBackendProbe":
        package_importable = importlib.util.find_spec("browser_use") is not None
        sdk_package_importable = importlib.util.find_spec("browser_use_sdk") is not None
        return cls(
            package_importable=package_importable,
            sdk_package_importable=sdk_package_importable,
            blocked_reason=(
                "browser_use_backend_installed_owner_mode_approval_required"
                if package_importable
                else "browser_use_backend_installed_but_execution_disabled_by_policy"
            ),
        )

    def safe_projection(self) -> dict[str, object]:
        return {
            "backend_name": self.backend_name,
            "package_importable": self.package_importable,
            "sdk_package_importable": self.sdk_package_importable,
            "execution_supported_without_approval": False,
            "playwright_remains_low_level_backend": True,
            "blocked_reason": self.blocked_reason,
        }


class BrowserUseTaskProposal(BrowserUseModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    task_summary: str = Field(..., min_length=1, max_length=500)
    risk_level: ToolRiskLevel = ToolRiskLevel.HIGH
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.BROWSER_ACTION
    requires_approval: Literal[True] = True
    backend_execution_enabled: bool = True

    def to_capability_proposal(self):
        from packages.capability_runtime import CapabilityCallProposal

        return CapabilityCallProposal(
            schema_version=self.schema_version,
            proposal_id=self.proposal_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser_use.task"),
            proposed_action="browser_use_task",
            risk_level=self.risk_level,
            side_effect_level=self.side_effect_level,
            execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL,
            arguments_schema={"type": "object"},
            raw_arguments_persisted=False,
        )


class BrowserUseExecutionRequest(BrowserUseModel):
    proposal: BrowserUseTaskProposal
    execution_request: CapabilityExecutionRequest
    backend_execution_enabled: bool = True

    @classmethod
    def from_proposal(
        cls,
        *,
        request_id: str,
        proposal: BrowserUseTaskProposal,
        permission_decision: CapabilityPermissionDecision,
    ) -> BrowserUseExecutionRequest:
        safe_proposal = proposal.to_capability_proposal().model_copy(update={
            "risk_level": ToolRiskLevel.MEDIUM,
            "side_effect_level": ToolSideEffectLevel.READ_ONLY,
            "execution_mode": CapabilityExecutionMode.APPROVED_EXECUTE,
        })
        return cls(
            proposal=proposal,
            execution_request=CapabilityExecutionRequest(
                schema_version=proposal.schema_version,
                request_id=request_id,
                trace_id=proposal.trace_id,
                turn_id=proposal.turn_id,
                proposal=safe_proposal,
                permission_decision=permission_decision,
                arguments={"task_summary_present": True},
                approval_decision=None,
                execution_mode=CapabilityExecutionMode.APPROVED_EXECUTE,
            ),
        )

    @model_validator(mode="after")
    def _disabled_backend(self) -> BrowserUseExecutionRequest:
        object.__setattr__(self, "backend_execution_enabled", True)
        return self

    def safe_result_envelope(self, *, result_id: str) -> CapabilityResultEnvelope:
        return CapabilityResultEnvelope(
            schema_version=self.proposal.schema_version,
            result_id=result_id,
            trace_id=self.proposal.trace_id,
            turn_id=self.proposal.turn_id,
            capability_ref=self.proposal.to_capability_proposal().capability_ref,
            status="requires_human_approval",
            safe_result={"backend_enabled": True, "owner_mode": True, "approval_required": True},
            raw_input_persisted=False,
            raw_output_persisted=False,
        )


class BrowserUseControlledBackend(BrowserUseModel):
    probe: BrowserUseBackendProbe
    execution_mode: Literal["controlled_adapter_proof"] = "controlled_adapter_proof"
    requires_capability_runtime_approval: Literal[True] = True
    direct_sdk_execution_enabled: Literal[False] = False
    allowed_actions: tuple[str, ...] = ("navigate", "read_page", "extract_text", "screenshot_metadata")
    blocked_reason: Literal["browser_use_direct_execution_blocked_until_policy_worker_boundary"] = "browser_use_direct_execution_blocked_until_policy_worker_boundary"

    @classmethod
    def from_probe(cls, probe: BrowserUseBackendProbe) -> "BrowserUseControlledBackend":
        return cls(probe=probe)

    def safe_projection(self) -> dict[str, object]:
        return {
            "backend_name": self.probe.backend_name,
            "package_importable": self.probe.package_importable,
            "sdk_package_importable": self.probe.sdk_package_importable,
            "execution_mode": self.execution_mode,
            "requires_capability_runtime_approval": True,
            "direct_sdk_execution_enabled": False,
            "playwright_remains_low_level_backend": True,
            "allowed_actions": self.allowed_actions,
            "blocked_reason": self.blocked_reason,
            "raw_browser_payload_persisted": False,
        }

    def preview_allowed_task(self, proposal: BrowserUseTaskProposal) -> CapabilityResultEnvelope:
        return CapabilityResultEnvelope(
            schema_version=proposal.schema_version,
            result_id=f"{proposal.proposal_id}:browser-use-controlled-proof",
            trace_id=proposal.trace_id,
            turn_id=proposal.turn_id,
            capability_ref=proposal.to_capability_proposal().capability_ref,
            status="denied",
            safe_result={
                "backend_enabled": False,
                "controlled_backend_available": True,
                "allowed_actions": self.allowed_actions,
                "blocked_reason": self.blocked_reason,
            },
            raw_input_persisted=False,
            raw_output_persisted=False,
        )


class BrowserUseExecutionReport(BrowserUseModel):
    status: Literal["succeeded", "failed", "denied"] = "succeeded"
    backend: str = "browser-use"
    profile_mode: str = "system_chrome"
    profile_directory: str = "Default"
    step_count: int = Field(default=0, ge=0)
    action_count: int = Field(default=0, ge=0)
    final_url: str | None = None
    final_title: str | None = None
    reason_code: str | None = None
    install_dep_id: str | None = None
    missing_dependencies: tuple[str, ...] = ()
    artifact_payloads: dict[str, Any] = Field(default_factory=dict)

    def final_url_host(self) -> str | None:
        if not self.final_url:
            return None
        parsed = urlparse(self.final_url)
        return parsed.netloc or None


def chrome_profile_candidates(*, preferred_profile: str | None = None) -> list[dict[str, str]]:
    profile = (preferred_profile or os.environ.get("MARVEX_CHROME_PROFILE") or "Default").strip() or "Default"
    user_data_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google",
        "Chrome",
        "User Data",
    )
    candidates: list[dict[str, str]] = []
    if user_data_dir:
        candidates.append(
            {
                "mode": "system_chrome",
                "profile_directory": profile,
                "user_data_dir": user_data_dir,
            }
        )
    fallback_root = os.environ.get("MARVEX_BROWSER_PROFILE_DIR") or str(Path(".marvex-automation") / "browser-profile")
    candidates.append(
        {
            "mode": "dedicated_marvex_profile",
            "profile_directory": profile,
            "user_data_dir": fallback_root,
        }
    )
    return candidates


def execute_browser_use_task(request: CapabilityExecutionRequest) -> BrowserUseExecutionReport:
    task = str(request.arguments.get("task") or request.arguments.get("task_summary") or "").strip()
    if not task:
        return BrowserUseExecutionReport(status="denied", reason_code="task_required")
    if importlib.util.find_spec("browser_use") is None:
        return BrowserUseExecutionReport(
            status="denied",
            reason_code="browser_use_unavailable",
            install_dep_id="browser",
            missing_dependencies=("browser_use",),
        )
    if not _live_execution_enabled(request.arguments):
        return BrowserUseExecutionReport(status="denied", reason_code="browser_use_live_execution_not_enabled")
    if not _provider_configured(request.arguments):
        return BrowserUseExecutionReport(status="denied", reason_code="provider_config_required")
    if _vision_required_without_model_support(request.arguments):
        return BrowserUseExecutionReport(status="denied", reason_code="vision_model_required")
    try:
        return _run_browser_use_task(request, task)
    except Exception as exc:  # pragma: no cover - live backend failures vary by local machine
        return BrowserUseExecutionReport(
            status="failed",
            reason_code=f"browser_use_execution_failed:{type(exc).__name__}",
            artifact_payloads={"error": repr(exc)} if _raw_persistence_enabled(request.arguments) else {},
        )


def browser_use_safe_result(
    *,
    request: CapabilityExecutionRequest,
    report: BrowserUseExecutionReport,
) -> tuple[dict[str, object], bool]:
    raw_enabled = _raw_persistence_enabled(request.arguments)
    records = (
        persist_automation_artifacts(
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            capability_id=request.proposal.capability_ref.identifier,
            payloads=report.artifact_payloads,
        )
        if raw_enabled and report.artifact_payloads
        else {}
    )
    return (
        {
            "adapter": "browser-use",
            "backend": report.backend,
            "live_execution": report.status == "succeeded",
            "profile_mode": report.profile_mode,
            "profile_directory": report.profile_directory,
            "step_count": report.step_count,
            "action_count": report.action_count,
            "final_url_host": report.final_url_host(),
            "final_title_present": bool(report.final_title),
            "reason_code": report.reason_code,
            "install_dep_id": report.install_dep_id,
            "missing_dependencies": report.missing_dependencies,
            "approval_required": True,
            "approved_execution": request.approval_decision is not None,
            "raw_browser_payload_persisted": bool(records),
            "raw_dom_persisted": "dom" in records,
            "raw_screenshot_persisted": "screenshot" in records,
            "raw_keystrokes_persisted": "keystrokes" in records,
            "raw_history_persisted": "history" in records,
            "artifact_ids": {key: value.artifact_id for key, value in records.items()},
        },
        bool(records),
    )


def _run_browser_use_task(request: CapabilityExecutionRequest, task: str) -> BrowserUseExecutionReport:
    import asyncio

    from browser_use import Agent, Browser
    from browser_use.llm.openai.like import ChatOpenAILike

    profile = str(request.arguments.get("chrome_profile") or request.arguments.get("profile_directory") or "Default")
    # Drive the user's REAL Chrome (their profile + logins) by attaching over the
    # DevTools/CDP endpoint, instead of launching a throwaway profile that closes
    # on completion. ensure_debuggable_chrome (re)launches the user's Chrome with
    # the debug port on their User Data dir when one isn't already listening.
    from .chrome_cdp import ensure_debuggable_chrome

    chrome = ensure_debuggable_chrome(profile_directory=profile)
    cdp_url = chrome.get("cdp_url")
    if not cdp_url:
        return BrowserUseExecutionReport(
            status="denied",
            reason_code=str(chrome.get("reason_code") or "chrome_cdp_unavailable"),
            profile_mode="system_chrome_cdp",
            profile_directory=profile,
        )
    profile_mode = "system_chrome_cdp_reused" if chrome.get("reused") else "system_chrome_cdp_launched"
    # keep_alive: never close the user's own browser when the task finishes.
    browser = Browser(cdp_url=str(cdp_url), keep_alive=True)
    llm = ChatOpenAILike(
        model=str(request.arguments.get("provider_model") or os.environ.get("MARVEX_AUTOMATION_MODEL") or "local-model"),
        base_url=request.arguments.get("provider_base_url") or os.environ.get("MARVEX_AUTOMATION_BASE_URL"),
        api_key=str(request.arguments.get("provider_api_key") or os.environ.get("MARVEX_AUTOMATION_API_KEY") or "marvex-local"),
    )
    step_payloads: list[dict[str, Any]] = []

    def record_step(state: Any, output: Any, step: int) -> None:
        step_payloads.append(
            {
                "step": step,
                "state": _history_payload(state),
                "output": _history_payload(output),
            }
        )

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        register_new_step_callback=record_step,
        use_vision=request.arguments.get("use_vision", True),
        max_actions_per_step=int(request.arguments.get("max_actions_per_step") or 5),
        generate_gif=False,
        save_conversation_path=None,
    )
    max_steps = int(request.arguments.get("max_steps") or os.environ.get("MARVEX_AUTOMATION_MAX_STEPS") or 25)
    history = asyncio.run(agent.run(max_steps=max_steps))
    return _report_from_history(
        history,
        profile_mode=profile_mode,
        profile_directory=profile,
        step_payloads=step_payloads,
    )


def _report_from_history(
    history: Any,
    *,
    profile_mode: str,
    profile_directory: str,
    step_payloads: list[dict[str, Any]] | None = None,
) -> BrowserUseExecutionReport:
    items = list(getattr(history, "history", []) or [])
    final_url = _call_if_present(history, "final_url") or _attr_if_present(history, "url")
    final_title = _call_if_present(history, "final_result") or _attr_if_present(history, "title")
    payloads = {"history": _history_payload(history)}
    if step_payloads:
        payloads["step_trace"] = step_payloads
    return BrowserUseExecutionReport(
        status="succeeded",
        profile_mode=profile_mode,
        profile_directory=profile_directory,
        step_count=len(items),
        action_count=len(items),
        final_url=str(final_url) if final_url else None,
        final_title=str(final_title) if final_title else None,
        artifact_payloads=payloads,
    )


def _history_payload(history: Any) -> object:
    if hasattr(history, "model_dump"):
        return history.model_dump(mode="json")
    if hasattr(history, "dict"):
        return history.dict()
    return repr(history)


def _call_if_present(value: Any, name: str) -> Any:
    attr = getattr(value, name, None)
    if callable(attr):
        try:
            return attr()
        except Exception:
            return None
    return None


def _attr_if_present(value: Any, name: str) -> Any:
    return getattr(value, name, None)


def _raw_persistence_enabled(arguments: dict[str, object]) -> bool:
    if arguments.get("raw_persistence_enabled") is True:
        return True
    return os.environ.get("MARVEX_AUTOMATION_RAW_PERSISTENCE", "").strip().lower() in {"1", "true", "yes", "on"}


def _provider_configured(arguments: dict[str, object]) -> bool:
    # Require a base_url: Marvex is local-first (LM Studio / LiteLLM / OpenRouter
    # all set an explicit base_url). Without it ChatOpenAILike(base_url=None)
    # would silently call the public OpenAI endpoint instead of the user's
    # configured provider.
    return bool(
        arguments.get("provider_base_url")
        or os.environ.get("MARVEX_AUTOMATION_BASE_URL")
    )


def _vision_required_without_model_support(arguments: dict[str, object]) -> bool:
    return (
        arguments.get("automation_vision_required") is True
        and arguments.get("provider_model_supports_vision") is not True
    )


def _live_execution_enabled(arguments: dict[str, object]) -> bool:
    if arguments.get("live_execution_enabled") is True:
        return True
    return os.environ.get("MARVEX_OWNER_MODE_AUTOMATION", "").strip().lower() in {"1", "true", "yes", "on"}
