from __future__ import annotations

from typing import Any

from .assets import VoiceAssetManager, VoiceModelInstallRequest
from .controller import VoiceWorkerController
from .models import VoiceWorkerCommand


class VoiceWorkerControlPlaneFacade:
    def __init__(self, controller: VoiceWorkerController | None = None, assets: VoiceAssetManager | None = None) -> None:
        self.controller = controller or VoiceWorkerController()
        self.assets = assets or self.controller.asset_manager

    def status(self) -> dict[str, object]:
        return self.controller.status().safe_projection()

    def devices(self) -> dict[str, object]:
        return {
            "schema_version": "1",
            "input_devices": [device.safe_projection() for device in self.controller.audio.list_input_devices()],
            "output_devices": [device.safe_projection() for device in self.controller.audio.list_output_devices()],
            "raw_audio_persisted": False,
        }

    def command(self, command: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        result = self.controller.handle(VoiceWorkerCommand(command=command, command_id=f"control-plane-{command}", payload=payload or {}))
        return _strip_raw_keys(result.model_dump(mode="json"))

    def install_model_voice(self, payload: dict[str, Any]) -> dict[str, object]:
        return self.assets.install_local(VoiceModelInstallRequest.model_validate(payload)).model_dump(mode="json")

    def remove_model_voice(self, payload: dict[str, Any]) -> dict[str, object]:
        return self.assets.remove(str(payload.get("model_id") or "")).model_dump(mode="json")

    def assets_status(self) -> dict[str, object]:
        return self.assets.registry().model_dump(mode="json")

    def start_wakeword_supervisor(self) -> dict[str, object]:
        return self.controller.start_wakeword_supervisor(explicit_user_triggered=True).safe_projection()

    def stop_wakeword_supervisor(self) -> dict[str, object]:
        return self.controller.stop_wakeword_supervisor(explicit_user_triggered=True).safe_projection()

    def tick_wakeword_supervisor(self) -> dict[str, object]:
        return self.controller.tick_wakeword_supervisor().safe_projection()

    def wakeword_supervisor_health(self) -> dict[str, object]:
        return self.controller.wakeword_supervisor_health().safe_projection()


def _strip_raw_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_raw_keys(item) for key, item in value.items() if not str(key).lower().startswith("raw_")}
    if isinstance(value, list):
        return [_strip_raw_keys(item) for item in value]
    return value
