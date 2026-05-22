from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest


def _load_windows_uia_module():
    module_path = Path(__file__).resolve().parents[2] / "packages" / "desktop_agent_runtime" / "windows_uia.py"
    spec = importlib.util.spec_from_file_location("test_windows_uia_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_projection_non_windows_is_safe_and_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    module = _load_windows_uia_module()
    projection = module.collect_projection()

    assert projection["available"] is False
    assert projection["platform"] == "linux"
    assert projection["raw_screen_persisted"] is False
    assert projection["raw_keystrokes_persisted"] is False
    assert projection["active_window"] is None
    assert projection["focused_control_path"] == []


def test_collect_projection_windows_calls_desktop_and_focused_control(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")

    class FakeWindow:
        element_info = type("ElementInfo", (), {"name": "Window With secret token"})()

        def friendly_class_name(self) -> str:
            return "Window"

    class FakeDesktop:
        def __init__(self, *, backend: str) -> None:
            assert backend == "uia"

        def get_active(self) -> FakeWindow:
            return FakeWindow()

    class FakeControl:
        Name = "Child secret value"
        ControlTypeName = "EditControl"

        def __init__(self, parent: "FakeControl | None") -> None:
            self._parent = parent

        def GetParentControl(self) -> "FakeControl | None":
            return self._parent

    root = FakeControl(None)
    root.Name = "Root token"
    root.ControlTypeName = "WindowControl"
    child = FakeControl(root)

    def fake_import_module(name: str):  # noqa: ANN001
        if name == "pywinauto":
            return type("PyWinAuto", (), {"Desktop": FakeDesktop})
        if name == "uiautomation":
            return type("UIAutomation", (), {"GetFocusedControl": lambda: child})
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    module = _load_windows_uia_module()
    projection = module.collect_projection()

    assert projection["available"] is True
    assert projection["active_window"]["class_name"] == "Window"
    assert "secret" not in projection["active_window"]["title"].lower()
    assert projection["focused_control_path"]
    assert projection["focused_control_path"][0]["control_type"] == "EditControl"
    assert projection["focused_control_path"][-1]["control_type"] == "WindowControl"
    assert projection["raw_screen_persisted"] is False
    assert projection["raw_keystrokes_persisted"] is False


def test_collect_projection_truncates_long_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")

    long_title = "A" * 500
    long_control_name = "B" * 500

    class FakeWindow:
        element_info = type("ElementInfo", (), {"name": long_title})()

        def friendly_class_name(self) -> str:
            return "Window"

    class FakeDesktop:
        def __init__(self, *, backend: str) -> None:
            assert backend == "uia"

        def get_active(self) -> FakeWindow:
            return FakeWindow()

    class FakeControl:
        Name = long_control_name
        ControlTypeName = "EditControl"

        def GetParentControl(self):  # noqa: ANN001
            return None

    def fake_import_module(name: str):  # noqa: ANN001
        if name == "pywinauto":
            return type("PyWinAuto", (), {"Desktop": FakeDesktop})
        if name == "uiautomation":
            return type("UIAutomation", (), {"GetFocusedControl": lambda: FakeControl()})
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    module = _load_windows_uia_module()
    projection = module.collect_projection(max_text_chars=64)

    assert len(projection["active_window"]["title"]) <= 64
    assert len(projection["focused_control_path"][0]["name"]) <= 64
