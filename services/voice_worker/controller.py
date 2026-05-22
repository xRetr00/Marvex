from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.voice_worker_runtime.controller import VoiceWorkerController
from packages.voice_worker_runtime.models import (
    VoiceWorkerCommand,
    VoiceWorkerHealth,
    VoiceWorkerVersionInfo,
)

from .models import (
    SERVICE_NAME,
    SERVICE_VERSION,
    VoiceWorkerServiceCommandResult,
    VoiceWorkerServiceConfig,
)


@dataclass
class VoiceWorkerServiceController:
    """Thin service-layer wrapper over packages.voice_worker_runtime.VoiceWorkerController.

    Audio, STT, TTS, and wakeword logic live exclusively in the runtime package.
    This wrapper owns only the service lifecycle (start/stop/status/health/version)
    and the JSONL entrypoint contract surface.
    """

    config: VoiceWorkerServiceConfig = field(default_factory=VoiceWorkerServiceConfig)
    _runtime: VoiceWorkerController = field(init=False)

    def __post_init__(self) -> None:
        self._runtime = VoiceWorkerController()

    def start(self, *, trace_id: str = "voice-worker-start") -> VoiceWorkerServiceCommandResult:
        self._runtime.handle(VoiceWorkerCommand(command="start", command_id=f"svc-{trace_id}"))
        return self._result(command="start", ok=True, trace_id=trace_id)

    def stop(self, *, trace_id: str = "voice-worker-stop") -> VoiceWorkerServiceCommandResult:
        self._runtime.handle(VoiceWorkerCommand(command="stop", command_id=f"svc-{trace_id}"))
        return self._result(command="stop", ok=True, trace_id=trace_id)

    def status(self, *, trace_id: str = "voice-worker-status") -> VoiceWorkerServiceCommandResult:
        return self._result(command="status", ok=True, trace_id=trace_id)

    def health(self) -> VoiceWorkerHealth:
        return self._runtime.health()

    def version(self) -> VoiceWorkerVersionInfo:
        return self._runtime.version()

    def handle_runtime_command(self, command: VoiceWorkerCommand) -> dict[str, Any]:
        result = self._runtime.handle(command)
        return result.safe_projection()

    def _lifecycle_state(self) -> str:
        return self._runtime.status().lifecycle_state.value

    def _result(
        self,
        *,
        command: str,
        ok: bool,
        trace_id: str,
        metadata: dict[str, object] | None = None,
    ) -> VoiceWorkerServiceCommandResult:
        return VoiceWorkerServiceCommandResult(
            command=command,  # type: ignore[arg-type]
            ok=ok,
            trace_id=trace_id,
            state=self._lifecycle_state(),
            metadata=dict(metadata or {
                "service": SERVICE_NAME,
                "service_version": SERVICE_VERSION,
                "raw_audio_persisted": False,
                "raw_transcript_persisted": False,
            }),
        )
