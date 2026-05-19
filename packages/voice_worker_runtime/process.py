from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceWorkerProcessSpec:
    module: str = "packages.voice_worker_runtime.worker_main"
    host: str = "127.0.0.1"
    port: int = 8767

    def argv(self) -> tuple[str, ...]:
        return (sys.executable, "-m", self.module, "--host", self.host, "--port", str(self.port))


class VoiceWorkerProcessAdapter:
    def __init__(self, spec: VoiceWorkerProcessSpec | None = None) -> None:
        self.spec = spec or VoiceWorkerProcessSpec()
        self._process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self._process = subprocess.Popen(self.spec.argv(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._process.terminate()
        self._process.wait(timeout=5)

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None
