from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Literal

from pydantic import Field

from packages.voice_runtime import AudioFrame, WakeWordDetectionResult
from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel, safe_mapping

from .assets import VoiceAssetManager
from .audio import LocalAudioAdapter
from .backend_runtime import VoiceWorkerBackendRuntime
from .models import VoiceWorkerConfig


WAKEWORD_SUPERVISOR_MODEL_ID = "hey-marvex"
_BENIGN_REASON_CODES = frozenset({"wakeword.detected", "wakeword.not_detected"})


class WakewordSupervisorLifecycleState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    HALTED = "halted"


class WakewordSupervisorPolicy(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    max_consecutive_failures: int = Field(default=3, ge=1)
    initial_backoff_ms: int = Field(default=250, ge=0)
    max_backoff_ms: int = Field(default=5_000, ge=0)
    health_check_interval_ms: int = Field(default=1_000, ge=0)
    auto_restart_enabled: bool = True
    explicit_visible_control_required: Literal[True] = True
    hidden_auto_start_allowed: Literal[False] = False
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False


class WakewordSupervisorTickResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    lifecycle_state: WakewordSupervisorLifecycleState
    detected: bool
    consecutive_failures: int
    current_backoff_ms: int
    tick_count: int = Field(default=0, ge=0)
    backend_id: str
    phrase: str
    exact_blocker: str | None = None
    next_tick_allowed_at: str | None = None
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping(self.model_dump(mode="json"))


class WakewordSupervisorHealth(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    lifecycle_state: WakewordSupervisorLifecycleState
    started: bool
    consecutive_failures: int
    current_backoff_ms: int
    tick_count: int = Field(default=0, ge=0)
    last_tick_at: str | None = None
    next_tick_allowed_at: str | None = None
    asset_ready: bool
    backend_id: str
    phrase: str
    auto_restart_enabled: bool
    explicit_visible_control_required: Literal[True] = True
    hidden_auto_start_allowed: Literal[False] = False
    exact_blocker: str | None = None
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping(self.model_dump(mode="json"))


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class WakewordWorkerSupervisor:
    """Explicit visible supervisor for the local wakeword worker loop.

    Responsibilities:
      * lifecycle management (start, stop, clean shutdown)
      * health checks (asset readiness, backend readiness, recent tick)
      * restart-on-failure with bounded exponential backoff
      * halt after consecutive failure threshold so the user can intervene

    Hidden auto-start is never allowed: every start/stop transition must be
    explicit-user-triggered. Detection runs only when the configured Hey Marvex
    asset is installed under the safe asset root and the configured wakeword
    backend package import is available. The supervisor does not persist raw
    audio, raw transcripts, or generated audio.
    """

    def __init__(
        self,
        *,
        config: VoiceWorkerConfig,
        asset_manager: VoiceAssetManager,
        backend_runtime: VoiceWorkerBackendRuntime,
        audio: LocalAudioAdapter,
        policy: WakewordSupervisorPolicy | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._config = config
        self._asset_manager = asset_manager
        self._backend_runtime = backend_runtime
        self._audio = audio
        self._policy = policy or WakewordSupervisorPolicy()
        self._clock = clock or _utc_now
        self._state: WakewordSupervisorLifecycleState = WakewordSupervisorLifecycleState.STOPPED
        self._consecutive_failures = 0
        self._current_backoff_ms = 0
        self._last_tick_at: datetime | None = None
        self._next_tick_allowed_at: datetime | None = None
        self._exact_blocker: str | None = None
        self._tick_counter = 0

    @property
    def lifecycle_state(self) -> WakewordSupervisorLifecycleState:
        return self._state

    @property
    def policy(self) -> WakewordSupervisorPolicy:
        return self._policy

    def update_config(self, config: VoiceWorkerConfig) -> None:
        self._config = config

    def start(self, *, explicit_user_triggered: bool = True) -> WakewordSupervisorHealth:
        if not explicit_user_triggered:
            self._state = WakewordSupervisorLifecycleState.STOPPED
            self._exact_blocker = "wakeword_supervisor.explicit_user_required"
            return self.health()
        if not self._config.wakeword.enabled:
            self._state = WakewordSupervisorLifecycleState.STOPPED
            self._exact_blocker = "wakeword_not_enabled"
            return self.health()
        if not self._asset_ready():
            self._state = WakewordSupervisorLifecycleState.STOPPED
            self._exact_blocker = "wakeword_model_not_installed"
            return self.health()
        self._state = WakewordSupervisorLifecycleState.STARTING
        self._consecutive_failures = 0
        self._current_backoff_ms = 0
        self._next_tick_allowed_at = self._clock()
        self._exact_blocker = None
        self._state = WakewordSupervisorLifecycleState.RUNNING
        return self.health()

    def stop(self, *, explicit_user_triggered: bool = True) -> WakewordSupervisorHealth:
        if not explicit_user_triggered:
            self._exact_blocker = "wakeword_supervisor.explicit_user_required"
            return self.health()
        self._state = WakewordSupervisorLifecycleState.STOPPED
        self._consecutive_failures = 0
        self._current_backoff_ms = 0
        self._next_tick_allowed_at = None
        self._exact_blocker = None
        return self.health()

    def clean_shutdown(self) -> WakewordSupervisorHealth:
        """Explicit final shutdown: stop the loop and clear transient counters."""

        self._state = WakewordSupervisorLifecycleState.STOPPED
        self._consecutive_failures = 0
        self._current_backoff_ms = 0
        self._next_tick_allowed_at = None
        self._exact_blocker = "wakeword_supervisor.clean_shutdown"
        return self.health()

    def tick(self, *, now: datetime | None = None) -> WakewordSupervisorTickResult:
        moment = now or self._clock()
        self._tick_counter += 1
        if self._state == WakewordSupervisorLifecycleState.HALTED:
            self._exact_blocker = "wakeword_supervisor.halted"
            return self._tick_result(detected=False, exact_blocker=self._exact_blocker)
        if self._state == WakewordSupervisorLifecycleState.STOPPED:
            self._exact_blocker = "wakeword_supervisor.not_started"
            return self._tick_result(detected=False, exact_blocker=self._exact_blocker)
        if not self._config.wakeword.enabled:
            self._state = WakewordSupervisorLifecycleState.STOPPED
            self._exact_blocker = "wakeword_not_enabled"
            return self._tick_result(detected=False, exact_blocker=self._exact_blocker)
        if not self._asset_ready():
            self._state = WakewordSupervisorLifecycleState.STOPPED
            self._exact_blocker = "wakeword_model_not_installed"
            return self._tick_result(detected=False, exact_blocker=self._exact_blocker)
        if self._next_tick_allowed_at is not None and moment < self._next_tick_allowed_at:
            return self._tick_result(detected=False, exact_blocker="wakeword_supervisor.backoff_active")
        frames = tuple(
            self._audio.capture_frames(
                device_id=self._config.audio.input_device_id,
                sample_rate=self._config.audio.sample_rate,
                channel_count=self._config.audio.channel_count,
                frame_count=4,
            )
        )
        detection: WakeWordDetectionResult = self._backend_runtime.test_wakeword(
            trace_id=f"wakeword-supervisor-tick-{self._tick_counter}",
            backend_id=self._config.wakeword.backend_id,
            frames=frames,
            phrase=self._config.wakeword.phrase,
            threshold=self._config.wakeword.threshold,
        )
        self._last_tick_at = moment
        if detection.detected or detection.reason_code in _BENIGN_REASON_CODES:
            self._consecutive_failures = 0
            self._current_backoff_ms = 0
            self._next_tick_allowed_at = moment
            self._exact_blocker = None
            self._state = WakewordSupervisorLifecycleState.RUNNING
            return self._tick_result(detected=detection.detected, exact_blocker=None)
        # treat as worker failure: bump count, apply backoff, halt at threshold
        self._consecutive_failures += 1
        self._exact_blocker = detection.reason_code or "wakeword_supervisor.unknown_failure"
        if self._consecutive_failures >= self._policy.max_consecutive_failures:
            self._state = WakewordSupervisorLifecycleState.HALTED
            self._next_tick_allowed_at = None
            return self._tick_result(detected=False, exact_blocker=self._exact_blocker)
        if not self._policy.auto_restart_enabled:
            self._state = WakewordSupervisorLifecycleState.HALTED
            self._next_tick_allowed_at = None
            return self._tick_result(detected=False, exact_blocker=self._exact_blocker)
        self._current_backoff_ms = _next_backoff_ms(
            current=self._current_backoff_ms,
            initial=self._policy.initial_backoff_ms,
            ceiling=self._policy.max_backoff_ms,
        )
        self._state = WakewordSupervisorLifecycleState.DEGRADED
        self._next_tick_allowed_at = moment + timedelta(milliseconds=self._current_backoff_ms)
        return self._tick_result(detected=False, exact_blocker=self._exact_blocker)

    def health(self) -> WakewordSupervisorHealth:
        return WakewordSupervisorHealth(
            lifecycle_state=self._state,
            started=self._state
            in {
                WakewordSupervisorLifecycleState.STARTING,
                WakewordSupervisorLifecycleState.RUNNING,
                WakewordSupervisorLifecycleState.DEGRADED,
            },
            consecutive_failures=self._consecutive_failures,
            current_backoff_ms=self._current_backoff_ms,
            tick_count=self._tick_counter,
            last_tick_at=self._last_tick_at.isoformat() if self._last_tick_at else None,
            next_tick_allowed_at=self._next_tick_allowed_at.isoformat()
            if self._next_tick_allowed_at
            else None,
            asset_ready=self._asset_ready(),
            backend_id=self._config.wakeword.backend_id,
            phrase=self._config.wakeword.phrase,
            auto_restart_enabled=self._policy.auto_restart_enabled,
            exact_blocker=self._exact_blocker,
        )

    def _asset_ready(self) -> bool:
        return self._asset_manager.is_ready(
            model_id=WAKEWORD_SUPERVISOR_MODEL_ID,
            backend_id=self._config.wakeword.backend_id,
            model_kind="wakeword",
        )

    def _tick_result(self, *, detected: bool, exact_blocker: str | None) -> WakewordSupervisorTickResult:
        return WakewordSupervisorTickResult(
            lifecycle_state=self._state,
            detected=detected,
            consecutive_failures=self._consecutive_failures,
            current_backoff_ms=self._current_backoff_ms,
            tick_count=self._tick_counter,
            backend_id=self._config.wakeword.backend_id,
            phrase=self._config.wakeword.phrase,
            exact_blocker=exact_blocker,
            next_tick_allowed_at=self._next_tick_allowed_at.isoformat()
            if self._next_tick_allowed_at
            else None,
        )


def _next_backoff_ms(*, current: int, initial: int, ceiling: int) -> int:
    if current <= 0:
        candidate = initial
    else:
        candidate = current * 2
    return max(initial, min(candidate, ceiling))
