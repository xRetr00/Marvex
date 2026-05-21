from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import subprocess

from packages.capability_runtime.approvals import ApprovalDecision
from packages.capability_runtime.autonomy import (
    AutonomyAction,
    AutonomyMode,
    AutonomyPolicy,
    PolicyDecision,
    evaluate_autonomy_action,
)
from packages.capability_runtime.governance_audit import (
    GovernanceDecisionType,
    GovernanceAction,
    GranularPermission,
    classify_governance_action,
)
from packages.capability_runtime.fake import DeterministicFakeCapabilityAdapter
from packages.capability_runtime.models import (
    CapabilityExecutionMode,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    HumanApprovalRequirement,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.capability_runtime.proposals import CapabilityCallProposal
from packages.capability_runtime.requests import CapabilityExecutionRequest
from packages.capability_runtime.results import CapabilityExecutionSummary, CapabilityResultEnvelope, SafeCapabilityProjection
from packages.contracts import HealthCheck, HealthStatus, VersionInfo
from packages.adapters.capabilities.builtins import BuiltinToolCatalog
from packages.adapters.capabilities.files import FileCapabilityError, ReadOnlyFileExecutor

from .models import (
    SCHEMA_VERSION,
    SERVICE_NAME,
    SERVICE_VERSION,
    ToolWorkerCommandResult,
    ToolWorkerConfig,
    ToolWorkerError,
)


class ToolWorkerState(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass
class ToolWorkerController:
    config: ToolWorkerConfig = field(default_factory=ToolWorkerConfig)

    def __post_init__(self) -> None:
        self._state = ToolWorkerState.INITIALIZED
        self._started_at = datetime.now(UTC)
        self._adapter = DeterministicFakeCapabilityAdapter()
        self._builtins = BuiltinToolCatalog.default()
        self._files = ReadOnlyFileExecutor()

    def start(self, *, trace_id: str = "tool-worker-start") -> ToolWorkerCommandResult:
        self._state = ToolWorkerState.RUNNING
        return self._result(command="start", ok=True, trace_id=trace_id)

    def stop(self, *, trace_id: str = "tool-worker-stop") -> ToolWorkerCommandResult:
        self._state = ToolWorkerState.STOPPING
        return self._result(command="stop", ok=True, trace_id=trace_id)

    def status(self, *, trace_id: str = "tool-worker-status") -> ToolWorkerCommandResult:
        return self._result(command="status", ok=True, trace_id=trace_id)

    def health(self) -> HealthCheck:
        return HealthCheck(
            schema_version=SCHEMA_VERSION,
            service=SERVICE_NAME,
            status=HealthStatus.OK
            if self._state != ToolWorkerState.STOPPING
            else HealthStatus.STOPPING,
            version=SERVICE_VERSION,
            uptime_seconds=max(0.0, (datetime.now(UTC) - self._started_at).total_seconds()),
            dependencies={"capability_runtime": {"configured": True}},
        )

    def version(self) -> VersionInfo:
        return VersionInfo(
            schema_version=SCHEMA_VERSION,
            service=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            contract_versions={
                "ToolWorker": SCHEMA_VERSION,
                "CapabilityRuntime": SCHEMA_VERSION,
                "CapabilityResultEnvelope": SCHEMA_VERSION,
                "SafeCapabilityProjection": SCHEMA_VERSION,
                "HealthCheck": SCHEMA_VERSION,
                "VersionInfo": SCHEMA_VERSION,
            },
            build={},
        )

    def execute(
        self,
        *,
        trace_id: str,
        turn_id: str,
        capability_id: str,
        action: str,
        capability: str,
        resource_type: str,
        arguments: dict[str, object],
        autonomy_mode: str | None = None,
    ) -> ToolWorkerCommandResult:
        capability_ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier=capability_id)
        risk_level = self._risk_level(capability)
        side_effect_level = self._side_effect_level(capability)
        policy = AutonomyPolicy.for_mode(_autonomy_mode(autonomy_mode or self.config.autonomy_mode))
        governance = classify_governance_action(
            GovernanceAction(
                requested_action=action,
                capability=capability,
                permission=_granular_permission(capability, action=action, resource_type=resource_type),
            )
        )
        audit = evaluate_autonomy_action(
            policy,
            AutonomyAction(
                action=action,
                resource_type=resource_type,
                capability=capability,
                risk_level=risk_level,
                safe_trace_ref=trace_id,
                user_approval_state="not_required",
            ),
        )

        blocking_decision = _blocking_decision(governance.decision, audit.decision)
        if blocking_decision != PolicyDecision.ALLOW:
            status = "requires_human_approval" if blocking_decision == PolicyDecision.APPROVAL_REQUIRED else "denied"
            result = CapabilityResultEnvelope(
                schema_version=SCHEMA_VERSION,
                result_id=f"{turn_id}:capability:result",
                trace_id=trace_id,
                turn_id=turn_id,
                capability_ref=capability_ref,
                status=status,
                safe_result={
                    "policy_decision": blocking_decision.value,
                    "governance_decision": governance.decision.value,
                    "autonomy_decision": audit.decision.value,
                },
                raw_input_persisted=False,
                raw_output_persisted=False,
            )
            summary = CapabilityExecutionSummary.from_result(
                result,
                readiness_count=1,
                eligible_count=0,
                denied_count=1,
                executed_fake_count=0,
            )
            return self._result(
                command="execute",
                ok=False,
                trace_id=trace_id,
                blocked=True,
                result=result,
                projection=SafeCapabilityProjection.from_summary(summary),
                policy_audit=_policy_projection(governance, audit),
                error=ToolWorkerError(
                    trace_id=trace_id,
                    turn_id=turn_id,
                    code=blocking_decision.value,
                    safe_message="Capability execution blocked by policy.",
                ),
            )

        proposal = CapabilityCallProposal(
            schema_version=SCHEMA_VERSION,
            proposal_id=f"{turn_id}:capability",
            trace_id=trace_id,
            turn_id=turn_id,
            capability_ref=capability_ref,
            proposed_action=action,
            risk_level=risk_level,
            side_effect_level=side_effect_level,
            execution_mode=CapabilityExecutionMode.APPROVED_EXECUTE,
            arguments_schema={"type": "object"},
            raw_arguments_persisted=False,
        )
        permission = CapabilityPermissionDecision(
            schema_version=SCHEMA_VERSION,
            decision_id=f"{proposal.proposal_id}:permission",
            capability_ref=capability_ref,
            decision="approved",
            reason_code="policy.matrix.allow",
            human_approval=HumanApprovalRequirement(
                required=False,
                reason_code="policy.not_required",
                prompt_user_visible=False,
                risk_level=risk_level,
                side_effect_level=side_effect_level,
            ),
        )
        approval = ApprovalDecision(
            schema_version=SCHEMA_VERSION,
            decision_id=f"{proposal.proposal_id}:approval",
            approval_request_id=f"{proposal.proposal_id}:approval-request",
            capability_ref=capability_ref,
            decision="approved",
            decided_by="policy",
            raw_decision_payload_persisted=False,
        )
        request = CapabilityExecutionRequest(
            schema_version=SCHEMA_VERSION,
            request_id=f"{proposal.proposal_id}:request",
            trace_id=trace_id,
            turn_id=turn_id,
            proposal=proposal,
            permission_decision=permission,
            arguments=self._execution_arguments(capability_id, arguments),
            raw_arguments_persisted=False,
        )
        if capability_id.startswith("builtin."):
            result = self._builtins.execute_request(
                request
            ).result
            summary = CapabilityExecutionSummary.from_result(
                result,
                readiness_count=1,
                eligible_count=1,
                denied_count=0,
                executed_fake_count=0,
            )
        elif capability_id in {"file.read", "file.list", "file.search"}:
            try:
                result = self._files.execute(request)
            except FileCapabilityError as exc:
                result = self._files.denial_result(request, code=exc.code)
                summary = CapabilityExecutionSummary.from_result(
                    result,
                    readiness_count=1,
                    eligible_count=0,
                    denied_count=1,
                    executed_fake_count=0,
                )
                return self._result(
                    command="execute",
                    ok=False,
                    trace_id=trace_id,
                    blocked=True,
                    result=result.model_copy(update={"result_id": f"{turn_id}:capability:result"}),
                    projection=SafeCapabilityProjection.from_summary(summary),
                    policy_audit=_policy_projection(governance, audit),
                    error=ToolWorkerError(
                        trace_id=trace_id,
                        turn_id=turn_id,
                        code=exc.code,
                        safe_message="File capability execution blocked.",
                    ),
                )
            summary = CapabilityExecutionSummary.from_result(
                result,
                readiness_count=1,
                eligible_count=1,
                denied_count=0,
                executed_fake_count=0,
            )
        else:
            result, summary = self._adapter.dispatch(
                proposal=proposal,
                permission_decision=permission,
                arguments={key: True for key in arguments},
            )
        result = result.model_copy(update={"result_id": f"{turn_id}:capability:result"})
        summary = CapabilityExecutionSummary.from_result(
            result,
            readiness_count=summary.capability_readiness_count,
            eligible_count=summary.selected_eligible_capability_count,
            denied_count=summary.denied_capability_count,
            executed_fake_count=summary.executed_fake_capability_count,
        )
        return self._result(
            command="execute",
            ok=True,
            trace_id=trace_id,
            result=result,
            projection=SafeCapabilityProjection.from_summary(summary),
            policy_audit=_policy_projection(governance, audit),
            metadata={
                "raw_arguments_persisted": False,
                "approval_decision": approval.decision,
            },
        )

    def _execution_arguments(self, capability_id: str, arguments: dict[str, object]) -> dict[str, object]:
        if capability_id != "builtin.repo_status":
            return dict(arguments)
        return {**_repo_status_arguments(), **dict(arguments)}

    def _risk_level(self, capability: str) -> ToolRiskLevel:
        if capability in {"file_write", "file_delete", "external_upload_send", "shell_command_execution"}:
            return ToolRiskLevel.HIGH
        return ToolRiskLevel.LOW

    def _side_effect_level(self, capability: str) -> ToolSideEffectLevel:
        if capability == "file_write":
            return ToolSideEffectLevel.WRITE_LOCAL
        if capability == "file_delete":
            return ToolSideEffectLevel.DESTRUCTIVE
        if capability == "external_upload_send":
            return ToolSideEffectLevel.NETWORK
        if capability == "shell_command_execution":
            return ToolSideEffectLevel.DESKTOP_ACTION
        if capability in {"read", "list", "search"}:
            return ToolSideEffectLevel.READ_ONLY
        return ToolSideEffectLevel.NONE

    def _result(
        self,
        *,
        command: str,
        ok: bool,
        trace_id: str,
        blocked: bool = False,
        result: CapabilityResultEnvelope | None = None,
        projection: SafeCapabilityProjection | None = None,
        policy_audit: dict[str, object] | None = None,
        error: ToolWorkerError | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ToolWorkerCommandResult:
        return ToolWorkerCommandResult(
            command=command,
            ok=ok,
            trace_id=trace_id,
            state=self._state.value,
            blocked=blocked,
            result=result,
            projection=projection,
            policy_audit=policy_audit,
            error=error,
            metadata=dict(metadata or {}),
        )

    def validation_result(self, *, trace_id: str, reason: str) -> ToolWorkerCommandResult:
        return self._result(
            command="execute",
            ok=False,
            trace_id=trace_id,
            error=ToolWorkerError(
                trace_id=trace_id,
                code="validation_error",
                safe_message="ToolWorker command validation failed.",
            ),
            metadata={"reason": reason, "raw_payload_persisted": False},
        )


def _repo_status_arguments() -> dict[str, object]:
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        ).stdout.strip() or "unknown"
        status = subprocess.run(
            ["git", "status", "--short"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        ).stdout
        return {"branch": branch[:120], "clean": status.strip() == "", "short_status": status[:4000]}
    except Exception:
        return {"branch": "unknown", "clean": False, "short_status": ""}


def _autonomy_mode(value: str) -> AutonomyMode:
    try:
        return AutonomyMode(value)
    except ValueError:
        return AutonomyMode.AUTO_MARVEX


def _granular_permission(capability: str, *, action: str, resource_type: str) -> GranularPermission:
    normalized = capability.lower().strip()
    action_text = action.lower()
    if normalized in {"read", "list", "search", "file_read"}:
        return GranularPermission.PUBLIC_READ
    if normalized in {"memory_search", "semantic_memory_search"}:
        return GranularPermission.MEMORY_READ
    if normalized in {"mcp_list"}:
        return GranularPermission.TOOL_LIST
    if normalized in {"file_write", "file_delete"} or any(marker in action_text for marker in ("write", "delete")):
        return GranularPermission.WRITE_LOCAL
    if normalized in {"external_upload_send"} or any(marker in action_text for marker in ("send", "upload")):
        return GranularPermission.SEND_EXTERNAL
    if normalized in {"browser_click_type", "computer_actions"}:
        return GranularPermission.BROWSER_SIDE_EFFECT
    if normalized == "shell_command_execution":
        return GranularPermission.EXECUTE_COMMAND
    if normalized in {"connectors_oauth", "live_oauth_sync"} or resource_type == "connector":
        return GranularPermission.CONNECT_ACCOUNT
    if normalized == "mcp_install_launch":
        return GranularPermission.ARBITRARY_EXECUTION
    if normalized == "mcp_execute":
        return GranularPermission.TOOL_LIST
    return GranularPermission.PUBLIC_READ


def _blocking_decision(governance_decision: GovernanceDecisionType, autonomy_decision: PolicyDecision) -> PolicyDecision:
    if governance_decision == GovernanceDecisionType.HARD_BLOCK:
        return PolicyDecision.HARD_BLOCK
    if governance_decision == GovernanceDecisionType.QUARANTINE:
        return PolicyDecision.QUARANTINE
    if governance_decision == GovernanceDecisionType.DENY:
        return PolicyDecision.DENY
    if governance_decision == GovernanceDecisionType.APPROVAL_REQUIRED or autonomy_decision == PolicyDecision.APPROVAL_REQUIRED:
        return PolicyDecision.APPROVAL_REQUIRED
    if autonomy_decision != PolicyDecision.ALLOW:
        return autonomy_decision
    return PolicyDecision.ALLOW


def _policy_projection(governance: object, autonomy: object) -> dict[str, object]:
    projection = dict(autonomy.safe_projection())
    projection.update({
        "governance": governance.safe_projection().model_dump(mode="json"),
        "autonomy": autonomy.safe_projection(),
    })
    return projection
