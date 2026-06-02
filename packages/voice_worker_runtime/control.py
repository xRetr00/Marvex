from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any
from typing import Callable

from .assets import VoiceAssetManager, VoiceModelCatalog, VoiceModelDownloadRequest, VoiceModelInstallRequest, load_voice_model_catalog
from .audio import SoundDeviceAudioAdapter
from .controller import VoiceWorkerController
from .models import VoiceWorkerCommand


class VoiceWorkerControlPlaneFacade:
    def __init__(
        self,
        controller: VoiceWorkerController | None = None,
        assets: VoiceAssetManager | None = None,
        model_catalog_loader: Callable[[], VoiceModelCatalog] = load_voice_model_catalog,
        tick_interval_seconds: float = 1.0,
    ) -> None:
        if controller is not None:
            self.controller = controller
        elif assets is not None:
            self.controller = VoiceWorkerController(asset_manager=assets)
        else:
            asset_root = os.environ.get("MARVEX_VOICE_ASSET_ROOT")
            audio = _default_audio_adapter()
            if asset_root and asset_root.strip():
                self.controller = VoiceWorkerController(audio=audio, asset_manager=VoiceAssetManager(asset_root=Path(asset_root)))
            else:
                self.controller = VoiceWorkerController(audio=audio)
        self.assets = assets or self.controller.asset_manager
        self._model_catalog_loader = model_catalog_loader
        self._tick_interval_seconds = tick_interval_seconds
        self._lock = threading.RLock()
        self._tick_stop = threading.Event()
        self._tick_thread: threading.Thread | None = None

    def status(self) -> dict[str, object]:
        with self._lock:
            self._refresh_assets()
            return self.controller.status().safe_projection()

    def devices(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema_version": "1",
                "input_devices": [device.safe_projection() for device in self.controller.audio.list_input_devices()],
                "output_devices": [device.safe_projection() for device in self.controller.audio.list_output_devices()],
                "raw_audio_persisted": False,
            }

    def command(self, command: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        should_start_tick = command in {"start", "resume", "reload_config"}
        should_stop_tick = command in {"stop", "pause"}
        with self._lock:
            result = self.controller.handle(VoiceWorkerCommand(command=command, command_id=f"control-plane-{command}", payload=payload or {}))
            payload_result = _strip_raw_keys(result.model_dump(mode="json"))
        if should_start_tick:
            self._ensure_tick_thread()
        if should_stop_tick:
            self._stop_tick_thread()
        return payload_result

    def install_model_voice(self, payload: dict[str, Any]) -> dict[str, object]:
        with self._lock:
            return self.assets.install_local(VoiceModelInstallRequest.model_validate(payload)).model_dump(mode="json")

    def download_model_voice(self, payload: dict[str, Any]) -> dict[str, object]:
        with self._lock:
            result = self.assets.download(VoiceModelDownloadRequest.model_validate(payload)).model_dump(mode="json")
            self._refresh_assets()
            return result

    def remove_model_voice(self, payload: dict[str, Any]) -> dict[str, object]:
        with self._lock:
            return self.assets.remove(str(payload.get("model_id") or "")).model_dump(mode="json")

    def assets_status(self) -> dict[str, object]:
        with self._lock:
            self._refresh_assets()
            return self.assets.registry().model_dump(mode="json")

    def model_catalog(self) -> dict[str, object]:
        return self._model_catalog_loader().model_dump(mode="json")

    def start_wakeword_supervisor(self) -> dict[str, object]:
        with self._lock:
            health = self.controller.start_wakeword_supervisor(explicit_user_triggered=True).safe_projection()
        self._ensure_tick_thread()
        return health

    def stop_wakeword_supervisor(self) -> dict[str, object]:
        with self._lock:
            health = self.controller.stop_wakeword_supervisor(explicit_user_triggered=True).safe_projection()
        self._stop_tick_thread()
        return health

    def tick_wakeword_supervisor(self) -> dict[str, object]:
        with self._lock:
            return self.controller.tick_wakeword_supervisor().safe_projection()

    def wakeword_supervisor_health(self) -> dict[str, object]:
        with self._lock:
            return self.controller.wakeword_supervisor_health().safe_projection()

    def _refresh_assets(self) -> None:
        self.assets.discover_installed(self._model_catalog_loader())

    def _ensure_tick_thread(self) -> None:
        if self._tick_thread is not None and self._tick_thread.is_alive():
            return
        self._tick_stop.clear()
        capture = _build_continuous_capture(self.controller)

        def tick_loop() -> None:
            if capture is not None:
                self.controller.run_wake_listen_loop(
                    capture=capture,
                    should_stop=self._tick_stop.is_set,
                    lock=self._lock,
                )
                return
            while not self._tick_stop.wait(max(0.01, self._tick_interval_seconds)):
                with self._lock:
                    status = self.controller.status()
                    if status.process_started and status.wakeword_supervisor_status.get("started") is True:
                        self.controller.tick_wakeword_supervisor()

        self._tick_thread = threading.Thread(target=tick_loop, name="marvex-control-plane-voice-wakeword", daemon=True)
        self._tick_thread.start()

    def _stop_tick_thread(self) -> None:
        self._tick_stop.set()
        thread = self._tick_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._tick_thread = None


def _strip_raw_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_raw_keys(item) for key, item in value.items() if not str(key).lower().startswith("raw_")}
    if isinstance(value, list):
        return [_strip_raw_keys(item) for item in value]
    return value


def _default_audio_adapter():
    try:
        adapter = SoundDeviceAudioAdapter()
        adapter.list_input_devices()
        return adapter
    except Exception:
        return None


def _build_continuous_capture(controller: VoiceWorkerController):
    if not isinstance(getattr(controller, "audio", None), SoundDeviceAudioAdapter):
        return None
    from .continuous_capture import SoundDeviceContinuousCapture

    cfg = controller.config
    device = cfg.audio.input_device_id
    resolved_device = int(device) if isinstance(device, str) and device.isdigit() else device
    return SoundDeviceContinuousCapture(
        sample_rate=cfg.audio.sample_rate,
        channels=cfg.audio.channel_count,
        frame_ms=cfg.audio.frame_duration_ms,
        device=resolved_device,
    )
