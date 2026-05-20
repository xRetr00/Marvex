from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from typing import Any, TextIO

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


def run_worker_contract_loop(
    *,
    controller: VoiceWorkerController,
    host: str,
    port: int,
    input_stream: TextIO,
    output_stream: TextIO,
) -> dict[str, Any]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("voice worker host must be loopback-only")
    final_status: dict[str, Any] = controller.status().safe_projection()
    for raw_line in input_stream:
        line = raw_line.strip()
        if not line:
            continue
        command_name = ""
        try:
            payload = json.loads(line)
            command_name = str(payload.get("command", "")) if isinstance(payload, dict) else ""
            command = VoiceWorkerCommand.model_validate(payload)
            result = controller.handle(command)
            response = result.safe_projection()
            final_status = result.status.safe_projection()
        except Exception:
            response = {
                "schema_version": "1",
                "command_id": "voice-worker-command-invalid",
                "error": {"reason_code": "voice_worker_command_invalid"},
                "raw_audio_persisted": False,
                "raw_transcript_persisted": False,
            }
        output_stream.write(json.dumps(response, sort_keys=True) + "\n")
        output_stream.flush()
        if isinstance(response, dict) and response.get("command_id") and command_name == "stop":
            break
    return {"host": host, "port": port, "status": final_status}


def main() -> int:
    parser = argparse.ArgumentParser(description="Marvex local voice worker runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--jsonl", action="store_true")
    args = parser.parse_args()
    controller = VoiceWorkerController()
    if args.jsonl:
        payload = run_worker_contract_loop(controller=controller, host=args.host, port=args.port, input_stream=__import__("sys").stdin, output_stream=__import__("sys").stdout)
    else:
        payload = run_worker_loop(controller=controller, host=args.host, port=args.port, once=args.once)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
