from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol

from packages.contracts import HealthCheck, HealthStatus, VersionInfo
from packages.desktop_agent_runtime.models import DesktopPerceptionSnapshot, DesktopRecallResult
from packages.desktop_agent_runtime.windows_uia import WindowsUIAutomationPerceptionAdapter

from .models import (
    SCHEMA_VERSION,
    SERVICE_NAME,
    SERVICE_VERSION,
    DesktopAgentCommandResult,
    DesktopAgentConfig,
    DesktopAgentError,
)


class DesktopPerceptionAdapter(Protocol):
    def focused_content(self, *, trace_id: str, content_budget_chars: int) -> DesktopPerceptionSnapshot: ...


class DesktopRecallAdapter(Protocol):
    def recall(self, *, trace_id: str, query: str, limit: int) -> DesktopRecallResult: ...


class DesktopAgentState(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass
class DesktopAgentController:
    config: DesktopAgentConfig = field(default_factory=DesktopAgentConfig)
    perception_adapter: DesktopPerceptionAdapter | None = None
    recall_adapter: DesktopRecallAdapter | None = None

    def __post_init__(self) -> None:
        self._state = DesktopAgentState.INITIALIZED
        self._started_at = datetime.now(UTC)
        if self.perception_adapter is None:
            self.perception_adapter = WindowsUIAutomationPerceptionAdapter()

    def start(self, *, trace_id: str = "desktop-agent-start") -> DesktopAgentCommandResult:
        self._state = DesktopAgentState.RUNNING
        return self._result(command="start", ok=True, trace_id=trace_id)

    def stop(self, *, trace_id: str = "desktop-agent-stop") -> DesktopAgentCommandResult:
        self._state = DesktopAgentState.STOPPING
        return self._result(command="stop", ok=True, trace_id=trace_id)

    def status(self, *, trace_id: str = "desktop-agent-status") -> DesktopAgentCommandResult:
        return self._result(command="status", ok=True, trace_id=trace_id)

    def health(self) -> HealthCheck:
        return HealthCheck(
            schema_version=SCHEMA_VERSION,
            service=SERVICE_NAME,
            status=HealthStatus.OK if self._state != DesktopAgentState.STOPPING else HealthStatus.STOPPING,
            version=SERVICE_VERSION,
            uptime_seconds=max(0.0, (datetime.now(UTC) - self._started_at).total_seconds()),
            dependencies={
                "pywinauto": {"required_on_windows": True},
                "uiautomation": {"required_on_windows": True},
                "screenpipe_mcp": {"configured": self.recall_adapter is not None},
            },
        )

    def version(self) -> VersionInfo:
        return VersionInfo(
            schema_version=SCHEMA_VERSION,
            service=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            contract_versions={
                "DesktopAgent": SCHEMA_VERSION,
                "DesktopPerceptionSnapshot": SCHEMA_VERSION,
                "DesktopRecallResult": SCHEMA_VERSION,
                "HealthCheck": SCHEMA_VERSION,
                "VersionInfo": SCHEMA_VERSION,
            },
            build={},
        )

    def perceive(self, *, trace_id: str, content_budget_chars: int | None = None) -> DesktopAgentCommandResult:
        try:
            snapshot = self.perception_adapter.focused_content(
                trace_id=trace_id,
                content_budget_chars=content_budget_chars or self.config.content_budget_chars,
            )
        except Exception:
            return self._result(
                command="perceive",
                ok=False,
                trace_id=trace_id,
                error=DesktopAgentError(
                    trace_id=trace_id,
                    code="desktop_agent_perception_failed",
                    safe_message="DesktopAgent perception failed safely.",
                ),
            )
        return self._result(
            command="perceive",
            ok=True,
            trace_id=trace_id,
            snapshot=snapshot,
            metadata={
                "local_only": True,
                "content_projection_only": True,
                "raw_screen_persisted": False,
                "raw_keystrokes_persisted": False,
            },
        )

    def recall(self, *, trace_id: str, query: str, limit: int = 5) -> DesktopAgentCommandResult:
        if self.recall_adapter is None:
            return self._result(
                command="recall",
                ok=False,
                trace_id=trace_id,
                error=DesktopAgentError(
                    trace_id=trace_id,
                    code="screenpipe_mcp_not_configured",
                    safe_message="Screenpipe MCP recall is not configured.",
                ),
                metadata={
                    "raw_screen_persisted": False,
                    "raw_audio_persisted": False,
                    "raw_transcript_persisted": False,
                    "raw_mcp_payload_persisted": False,
                },
            )
        recall = self.recall_adapter.recall(trace_id=trace_id, query=query, limit=limit)
        return self._result(command="recall", ok=True, trace_id=trace_id, recall=recall)

    def validation_result(self, *, trace_id: str, reason: str) -> DesktopAgentCommandResult:
        return self._result(
            command="status",
            ok=False,
            trace_id=trace_id,
            error=DesktopAgentError(
                trace_id=trace_id,
                code="validation_error",
                safe_message="DesktopAgent command validation failed.",
            ),
            metadata={"reason": reason, "raw_payload_persisted": False},
        )

    def _result(
        self,
        *,
        command: str,
        ok: bool,
        trace_id: str,
        snapshot: DesktopPerceptionSnapshot | None = None,
        recall: DesktopRecallResult | None = None,
        error: DesktopAgentError | None = None,
        metadata: dict[str, object] | None = None,
    ) -> DesktopAgentCommandResult:
        return DesktopAgentCommandResult(
            command=command,
            ok=ok,
            trace_id=trace_id,
            state=self._state.value,
            snapshot=snapshot,
            recall=recall,
            error=error,
            metadata=dict(metadata or {}),
        )
