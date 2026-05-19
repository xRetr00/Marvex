from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class VoiceWorkerProcessSpec:
    module: str = "packages.voice_worker_runtime.worker_main"
    host: str = "127.0.0.1"
    port: int = 8767

    def __post_init__(self) -> None:
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("voice worker process host must be loopback-only")

    def argv(self) -> tuple[str, ...]:
        return (sys.executable, "-m", self.module, "--host", self.host, "--port", str(self.port))


class VoiceWorkerProcessAdapter:
    def __init__(self, spec: VoiceWorkerProcessSpec | None = None, process_factory: Callable[..., Any] | None = None) -> None:
        self.spec = spec or VoiceWorkerProcessSpec()
        self._process_factory = process_factory or subprocess.Popen
        self._process: Any | None = None

    def start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self._process = self._process_factory(self.spec.argv(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)

    def stop(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._process.terminate()
        self._process.wait(timeout=5)

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None
