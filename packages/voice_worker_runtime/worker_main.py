from __future__ import annotations

import argparse
import json

from .controller import VoiceWorkerController
from .models import VoiceWorkerCommand


def main() -> int:
    parser = argparse.ArgumentParser(description="Marvex local voice worker runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    controller = VoiceWorkerController()
    result = controller.handle(VoiceWorkerCommand(command="start", command_id="voice-worker-main-start"))
    print(json.dumps({"host": args.host, "port": args.port, "status": result.status.safe_projection()}, sort_keys=True))
    if args.once:
        controller.handle(VoiceWorkerCommand(command="stop", command_id="voice-worker-main-stop"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
