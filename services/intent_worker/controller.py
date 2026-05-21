from __future__ import annotations

import contextlib
import io
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from packages.contracts import ErrorCode, ErrorEnvelope, HealthCheck, HealthStatus, VersionInfo
from packages.intent_runtime.models import IntentClassificationRequest, classify_intent

from .models import (
    SCHEMA_VERSION,
    SERVICE_NAME,
    SERVICE_VERSION,
    IntentWorkerCommandResult,
    IntentWorkerConfig,
)


class IntentWorkerState(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass
class IntentWorkerController:
    config: IntentWorkerConfig = field(default_factory=IntentWorkerConfig)

    def __post_init__(self) -> None:
        self._state = IntentWorkerState.INITIALIZED
        self._started_at = datetime.now(UTC)

    def start(self, *, trace_id: str = "intent-worker-start") -> IntentWorkerCommandResult:
        self._state = IntentWorkerState.RUNNING
        return self._result(command="start", ok=True, trace_id=trace_id)

    def stop(self, *, trace_id: str = "intent-worker-stop") -> IntentWorkerCommandResult:
        self._state = IntentWorkerState.STOPPING
        return self._result(command="stop", ok=True, trace_id=trace_id)

    def status(self, *, trace_id: str = "intent-worker-status") -> IntentWorkerCommandResult:
        return self._result(command="status", ok=True, trace_id=trace_id)

    def health(self) -> HealthCheck:
        return HealthCheck(
            schema_version=SCHEMA_VERSION,
            service=SERVICE_NAME,
            status=HealthStatus.OK
            if self._state != IntentWorkerState.STOPPING
            else HealthStatus.STOPPING,
            version=SERVICE_VERSION,
            uptime_seconds=max(0.0, (datetime.now(UTC) - self._started_at).total_seconds()),
            dependencies={"intent_runtime": {"configured": True}},
        )

    def version(self) -> VersionInfo:
        return VersionInfo(
            schema_version=SCHEMA_VERSION,
            service=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            contract_versions={
                "IntentWorker": SCHEMA_VERSION,
                "IntentClassificationRequest": SCHEMA_VERSION,
                "SafeIntentProjection": SCHEMA_VERSION,
                "ErrorEnvelope": SCHEMA_VERSION,
                "HealthCheck": SCHEMA_VERSION,
                "VersionInfo": SCHEMA_VERSION,
            },
            build={},
        )

    def classify(
        self,
        *,
        trace_id: str,
        turn_id: str,
        user_input_summary: str,
    ) -> IntentWorkerCommandResult:
        summary = self._safe_summary(user_input_summary)
        if not summary:
            return self._validation_result(trace_id=trace_id, reason="missing_user_input_summary")
        request = IntentClassificationRequest(
            schema_version=SCHEMA_VERSION,
            trace_id=trace_id,
            turn_id=turn_id,
            user_input_summary=summary,
            raw_input_persisted=False,
        )
        with contextlib.redirect_stderr(io.StringIO()), _suppress_stderr_fd():
            result = classify_intent(request)
        return self._result(
            command="classify",
            ok=True,
            trace_id=trace_id,
            classification=result.safe_projection(),
            backend_name=result.backend_name,
            metadata={
                "raw_input_persisted": False,
                "input_summary_truncated": len(user_input_summary) > len(summary),
            },
        )

    def _safe_summary(self, value: str) -> str:
        return value.strip()[: self.config.max_input_summary_chars]

    def _result(
        self,
        *,
        command: str,
        ok: bool,
        trace_id: str,
        classification: object | None = None,
        backend_name: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> IntentWorkerCommandResult:
        return IntentWorkerCommandResult(
            command=command,
            ok=ok,
            trace_id=trace_id,
            state=self._state.value,
            classification=classification,
            backend_name=backend_name,
            metadata=dict(metadata or {}),
        )

    def _validation_result(self, *, trace_id: str, reason: str) -> IntentWorkerCommandResult:
        return IntentWorkerCommandResult(
            command="classify",
            ok=False,
            trace_id=trace_id,
            state=self._state.value,
            error=ErrorEnvelope(
                schema_version=SCHEMA_VERSION,
                trace_id=trace_id,
                error_id=f"{trace_id}:intent-worker:{reason}",
                code=ErrorCode.VALIDATION_ERROR,
                message="IntentWorker command validation failed.",
                recoverable=False,
                source="intent_worker",
                details={"reason": reason},
            ),
            metadata={"raw_input_persisted": False},
        )


@contextlib.contextmanager
def _suppress_stderr_fd():
    try:
        saved_fd = os.dup(2)
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            os.dup2(devnull.fileno(), 2)
            try:
                yield
            finally:
                os.dup2(saved_fd, 2)
                os.close(saved_fd)
    except OSError:
        yield
