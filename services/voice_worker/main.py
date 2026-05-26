from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from packages.voice_worker_runtime.assets import VoiceAssetManager
from packages.voice_worker_runtime import SoundDeviceAudioAdapter
from packages.voice_worker_runtime.controller import VoiceWorkerController
from packages.voice_worker_runtime.worker_main import run_worker_contract_loop, run_worker_loop

from services.voice_worker.controller import VoiceWorkerServiceController
from services.voice_worker.models import SERVICE_NAME, SERVICE_VERSION


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8767


def run_health_once() -> int:
    controller = VoiceWorkerServiceController()
    health = controller.health()
    print(json.dumps(health.model_dump(mode="json"), sort_keys=True))
    return 0


def run_version_once() -> int:
    controller = VoiceWorkerServiceController()
    version = controller.version()
    version_data = version.safe_projection()
    version_data["service"] = SERVICE_NAME
    version_data["service_version"] = SERVICE_VERSION
    print(json.dumps(version_data, sort_keys=True))
    return 0


def _controller() -> VoiceWorkerController:
    """Build the worker controller, honoring a bundled/installed voice-asset
    root via MARVEX_VOICE_ASSET_ROOT (set by the installer/service) so shipped
    "Hey Marvex" models are found offline."""
    asset_root = os.environ.get("MARVEX_VOICE_ASSET_ROOT")
    audio = _audio_adapter()
    if asset_root and asset_root.strip():
        return VoiceWorkerController(audio=audio, asset_manager=VoiceAssetManager(asset_root=Path(asset_root)))
    return VoiceWorkerController(audio=audio)


def _audio_adapter():
    try:
        adapter = SoundDeviceAudioAdapter()
        adapter.list_input_devices()
        return adapter
    except Exception:
        return None


def run_once(*, host: str, port: int) -> int:
    runtime = _controller()
    payload = run_worker_loop(controller=runtime, host=host, port=port, once=True)
    print(json.dumps(payload, sort_keys=True))
    return 0


def run_jsonl(*, host: str, port: int) -> int:
    runtime = _controller()
    run_worker_contract_loop(
        controller=runtime,
        host=host,
        port=port,
        input_stream=sys.stdin,
        output_stream=sys.stdout,
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="VoiceWorker local JSONL process entrypoint."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--jsonl",
        action="store_true",
        help="Run JSONL contract loop (stdin/stdout VoiceWorkerCommand->VoiceWorkerCommandResult)",
    )
    mode.add_argument("--once", action="store_true", help="Start, emit status, then stop")
    mode.add_argument("--health-once", action="store_true", help="Emit health JSON and exit")
    mode.add_argument("--version-once", action="store_true", help="Emit version JSON and exit")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Loopback host (default: 127.0.0.1)",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port (default: 8767)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.health_once:
        return run_health_once()
    if args.version_once:
        return run_version_once()
    if args.once:
        return run_once(host=args.host, port=args.port)
    if args.jsonl:
        return run_jsonl(host=args.host, port=args.port)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
