from __future__ import annotations

from types import SimpleNamespace

from services.voice_worker.main import _controller
from packages.voice_worker_runtime import SoundDeviceAudioAdapter


def test_packaged_voice_worker_controller_uses_sounddevice_adapter_when_available(monkeypatch) -> None:
    fake_sd = SimpleNamespace(query_devices=lambda: ())
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", fake_sd)

    controller = _controller()

    assert isinstance(controller.audio, SoundDeviceAudioAdapter)
