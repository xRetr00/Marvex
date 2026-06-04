from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from packages.contracts import (
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    HealthCheck,
    HealthStatus,
    VersionInfo,
)
from packages.ports.core_service_port import CoreTurnExecutorPort


SCHEMA_VERSION = "0.1.1-draft"
SERVICE_NAME = "marvex-core-service"
SERVICE_VERSION = "0.2.1"
CONTRACT_VERSIONS = {
    "CoreService": SCHEMA_VERSION,
    "HealthCheck": SCHEMA_VERSION,
    "VersionInfo": SCHEMA_VERSION,
    "AssistantTurnInput": SCHEMA_VERSION,
    "AssistantTurnResult": SCHEMA_VERSION,
    "ErrorEnvelope": SCHEMA_VERSION,
}

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CoreServiceState(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass(frozen=True)
class CoreServiceConfig:
    service_name: str = SERVICE_NAME
    service_version: str = SERVICE_VERSION
    schema_version: str = SCHEMA_VERSION
    started_at: datetime = field(default_factory=_utc_now)
    clock: Clock = _utc_now
    contract_versions: Mapping[str, object] = field(
        default_factory=lambda: dict(CONTRACT_VERSIONS)
    )
    build: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.service_name.strip():
            raise ValueError("service_name must be non-empty")
        if not self.service_version.strip():
            raise ValueError("service_version must be non-empty")
        if not self.schema_version.strip():
            raise ValueError("schema_version must be non-empty")
        object.__setattr__(self, "contract_versions", dict(self.contract_versions))
        object.__setattr__(self, "build", dict(self.build))


class CoreService:
    def __init__(
        self,
        *,
        turn_executor: CoreTurnExecutorPort,
        config: CoreServiceConfig | None = None,
        started_at: datetime | None = None,
        clock: Clock | None = None,
    ) -> None:
        if not isinstance(turn_executor, CoreTurnExecutorPort):
            raise TypeError("turn_executor must implement CoreTurnExecutorPort")
        if config is not None and (started_at is not None or clock is not None):
            raise ValueError("use config or started_at/clock overrides, not both")
        self._turn_executor = turn_executor
        self._config = config or CoreServiceConfig(
            started_at=started_at or _utc_now(),
            clock=clock or _utc_now,
        )
        self._state = CoreServiceState.INITIALIZED

    def start(self) -> HealthCheck:
        if self._state != CoreServiceState.STOPPING:
            self._state = CoreServiceState.RUNNING
        return self.get_health()

    def shutdown(self) -> HealthCheck:
        self._state = CoreServiceState.STOPPING
        shutdown = getattr(self._turn_executor, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown()
            except Exception:
                pass
        return self.get_health()

    def get_health(self) -> HealthCheck:
        return HealthCheck(
            schema_version=self._config.schema_version,
            service=self._config.service_name,
            status=self._health_status(),
            version=self._config.service_version,
            uptime_seconds=self._uptime_seconds(),
            dependencies=self._dependencies(),
        )

    def get_version(self) -> VersionInfo:
        return VersionInfo(
            schema_version=self._config.schema_version,
            service=self._config.service_name,
            service_version=self._config.service_version,
            contract_versions=dict(self._config.contract_versions),
            build=dict(self._config.build),
        )

    def submit_turn(
        self,
        turn_input: AssistantTurnInput,
        previous_response_id: str | None = None,
        resume_approval_id: str | None = None,
        approval_decision: str | None = None,
    ) -> AssistantTurnResult:
        if self._state == CoreServiceState.INITIALIZED:
            return self._error_result(
                turn_input,
                code=ErrorCode.SERVICE_UNHEALTHY,
                message="CoreService is not started.",
                recoverable=True,
                reason="service_not_started",
            )
        if self._state == CoreServiceState.STOPPING:
            return self._error_result(
                turn_input,
                code=ErrorCode.SERVICE_UNHEALTHY,
                message="CoreService is shutting down.",
                recoverable=True,
                reason="service_shutting_down",
            )
        try:
            raw_result = self._turn_executor.submit_turn(
                turn_input,
                previous_response_id=previous_response_id,
                resume_approval_id=resume_approval_id,
                approval_decision=approval_decision,
            )
            result = AssistantTurnResult.model_validate(raw_result)
        except Exception:
            return self._error_result(
                turn_input,
                code=ErrorCode.INTERNAL_ERROR,
                message="CoreService turn execution failed.",
                recoverable=False,
                reason="turn_executor_failure",
            )

        if (
            result.schema_version != turn_input.schema_version
            or result.trace_id != turn_input.trace_id
            or result.turn_id != turn_input.turn_id
        ):
            return self._error_result(
                turn_input,
                code=ErrorCode.VALIDATION_ERROR,
                message="CoreService turn result envelope mismatch.",
                recoverable=False,
                reason="result_envelope_mismatch",
            )
        return result

    def _health_status(self) -> HealthStatus:
        if self._state == CoreServiceState.RUNNING:
            return HealthStatus.OK
        if self._state == CoreServiceState.STOPPING:
            return HealthStatus.STOPPING
        return HealthStatus.STARTING

    def _uptime_seconds(self) -> float:
        return max(0.0, (self._config.clock() - self._config.started_at).total_seconds())

    def _dependencies(self) -> dict[str, object]:
        return {
            "turn_executor": {"configured": True},
            "accepting_turns": self._state == CoreServiceState.RUNNING,
        }

    def _error_result(
        self,
        turn_input: AssistantTurnInput,
        *,
        code: ErrorCode,
        message: str,
        recoverable: bool,
        reason: str,
    ) -> AssistantTurnResult:
        return AssistantTurnResult(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            assistant_final_response=None,
            output_events=[],
            stage_summaries=[],
            provider_turn_refs=[],
            tool_result_refs=[],
            memory_result_refs=[],
            session_result_ref=None,
            error=ErrorEnvelope(
                schema_version=turn_input.schema_version,
                trace_id=turn_input.trace_id,
                error_id=f"{turn_input.turn_id}:core-service:{reason}",
                code=code,
                message=message,
                recoverable=recoverable,
                source="core_service",
                details={"reason": reason},
            ),
            metadata={},
        )
