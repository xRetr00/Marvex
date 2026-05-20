from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from .models import VoiceWorkerCommand


@dataclass(frozen=True)
class VoiceWorkerProcessSpec:
    module: str = "packages.voice_worker_runtime.worker_main"
    host: str = "127.0.0.1"
    port: int = 8767

    def __post_init__(self) -> None:
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("voice worker process host must be loopback-only")

    def argv(self) -> tuple[str, ...]:
        return (sys.executable, "-m", self.module, "--host", self.host, "--port", str(self.port), "--jsonl")


class VoiceWorkerProcessAdapter:
    def __init__(self, spec: VoiceWorkerProcessSpec | None = None, process_factory: Callable[..., Any] | None = None) -> None:
        self.spec = spec or VoiceWorkerProcessSpec()
        self._process_factory = process_factory or subprocess.Popen
        self._process: Any | None = None

    def start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self._process = self._process_factory(self.spec.argv(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False, text=True)

    def stop(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._process.terminate()
        self._process.wait(timeout=5)

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def send_command(self, command: VoiceWorkerCommand) -> dict[str, Any]:
        if self._process is None or self._process.poll() is not None:
            raise RuntimeError("voice worker process is not running")
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("voice worker process contract pipes are not available")
        self._process.stdin.write(command.model_dump_json() + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        payload = json.loads(line or "{}")
        return payload if isinstance(payload, dict) else {}


class VoiceWorkerProcessSupervisor:
    """Manages VoiceWorkerProcessAdapter lifecycle with restart-on-crash and bounded backoff.

    This supervisor lives at the service layer and owns the process boundary.
    It does NOT manage the model-level pipeline, backends, or audio — those are
    internal to the worker subprocess.  Call ``check()`` on a regular interval
    from a service heartbeat loop to detect and restart crashed processes.

    Governance: local-only; no remote binding; explicit ``start()``/``stop()``
    required.  Hidden auto-start is forbidden: always supply
    ``explicit_user_triggered=True`` intent at the service call site.
    """

    def __init__(
        self,
        *,
        adapter: VoiceWorkerProcessAdapter | None = None,
        max_consecutive_restarts: int = 5,
        initial_backoff_s: float = 1.0,
        max_backoff_s: float = 30.0,
        auto_restart: bool = True,
    ) -> None:
        self._adapter = adapter or VoiceWorkerProcessAdapter()
        self._max_consecutive_restarts = max_consecutive_restarts
        self._initial_backoff_s = initial_backoff_s
        self._max_backoff_s = max_backoff_s
        self._auto_restart = auto_restart
        self._consecutive_restarts = 0
        self._current_backoff_s = 0.0
        self._started = False
        self._halted = False
        self._last_restart_at: datetime | None = None

    def start(self) -> dict[str, object]:
        """Start the worker process.  Must be called with explicit user intent."""
        if self._halted:
            return self._safe_status("halted", "supervisor_halted_max_restarts_exceeded")
        self._adapter.start()
        self._started = True
        self._consecutive_restarts = 0
        self._current_backoff_s = 0.0
        return self._safe_status("running")

    def stop(self) -> dict[str, object]:
        """Stop the worker process cleanly."""
        self._adapter.stop()
        self._started = False
        return self._safe_status("stopped")

    def check(self) -> dict[str, object]:
        """Check process health; restart if crashed and policy allows.

        Call this from a service heartbeat loop.  Returns a safe status dict
        that includes the current lifecycle state and restart counters.  Never
        persists raw audio or transcripts.
        """
        if not self._started:
            return self._safe_status("stopped")
        if self._halted:
            return self._safe_status("halted", "supervisor_halted_max_restarts_exceeded")
        if self._adapter.is_running():
            self._consecutive_restarts = 0
            self._current_backoff_s = 0.0
            return self._safe_status("running")
        # Process exited unexpectedly.
        if not self._auto_restart:
            self._halted = True
            return self._safe_status("halted", "process_exited_auto_restart_disabled")
        self._consecutive_restarts += 1
        if self._consecutive_restarts > self._max_consecutive_restarts:
            self._halted = True
            return self._safe_status("halted", "max_consecutive_restarts_exceeded")
        self._current_backoff_s = _next_backoff_s(
            current=self._current_backoff_s,
            initial=self._initial_backoff_s,
            ceiling=self._max_backoff_s,
        )
        self._last_restart_at = datetime.now(UTC)
        self._adapter.start()
        return self._safe_status("restarted", "process_exited_restarted")

    def is_running(self) -> bool:
        return self._adapter.is_running()

    def send_command(self, command: VoiceWorkerCommand) -> dict[str, Any]:
        return self._adapter.send_command(command)

    def safe_status(self) -> dict[str, object]:
        state = "running" if self._adapter.is_running() else ("halted" if self._halted else "stopped")
        return self._safe_status(state)

    def _safe_status(self, state: str, reason_code: str = "") -> dict[str, object]:
        return {
            "state": state,
            "consecutive_restarts": self._consecutive_restarts,
            "current_backoff_s": self._current_backoff_s,
            "halted": self._halted,
            "auto_restart": self._auto_restart,
            "max_consecutive_restarts": self._max_consecutive_restarts,
            "reason_code": reason_code,
            "last_restart_at": self._last_restart_at.isoformat() if self._last_restart_at else None,
            "raw_audio_persisted": False,
        }


def _next_backoff_s(*, current: float, initial: float, ceiling: float) -> float:
    if current <= 0:
        return initial
    return min(current * 2, ceiling)
