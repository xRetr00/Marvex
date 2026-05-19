from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from typing import Any

from .controller import VoiceWorkerController
from .models import VoiceWorkerCommand


def run_worker_loop(
    *,
    controller: VoiceWorkerController,
    host: str,
    port: int,
    once: bool = False,
    should_stop: Callable[[], bool] | None = None,
    sleep_seconds: float = 1.0,
) -> dict[str, Any]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("voice worker host must be loopback-only")
    result = controller.handle(VoiceWorkerCommand(command="start", command_id="voice-worker-main-start"))
    payload = {"host": host, "port": port, "status": result.status.safe_projection()}
    if once:
        controller.handle(VoiceWorkerCommand(command="stop", command_id="voice-worker-main-stop"))
        return payload
    stop = should_stop or (lambda: False)
    try:
        while not stop():
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        controller.handle(VoiceWorkerCommand(command="stop", command_id="voice-worker-main-stop"))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Marvex local voice worker runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    controller = VoiceWorkerController()
    payload = run_worker_loop(controller=controller, host=args.host, port=args.port, once=args.once)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
