"""Chrome CDP launcher for real-browser automation (browser_use/playwright)."""

from __future__ import annotations

from pathlib import Path

from packages.adapters.capabilities import chrome_cdp


def test_cdp_port_env_override_and_default(monkeypatch):
    monkeypatch.delenv("MARVEX_CHROME_CDP_PORT", raising=False)
    assert chrome_cdp.chrome_cdp_port() == chrome_cdp.DEFAULT_CDP_PORT
    monkeypatch.setenv("MARVEX_CHROME_CDP_PORT", "9333")
    assert chrome_cdp.chrome_cdp_port() == 9333
    monkeypatch.setenv("MARVEX_CHROME_CDP_PORT", "not-a-port")
    assert chrome_cdp.chrome_cdp_port() == chrome_cdp.DEFAULT_CDP_PORT


def test_chrome_executable_env_override(monkeypatch, tmp_path):
    fake = tmp_path / "chrome.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setenv("MARVEX_CHROME_PATH", str(fake))
    assert chrome_cdp.chrome_executable_path() == str(fake)


def test_reuses_already_running_endpoint(monkeypatch):
    monkeypatch.setattr(chrome_cdp, "cdp_endpoint_alive", lambda port, **_: True)
    result = chrome_cdp.ensure_debuggable_chrome(port=9222)
    assert result == {
        "cdp_url": "http://127.0.0.1:9222",
        "port": 9222,
        "launched": False,
        "reused": True,
        "reason_code": None,
    }


def test_no_launch_when_disabled_and_not_alive(monkeypatch):
    monkeypatch.setattr(chrome_cdp, "cdp_endpoint_alive", lambda port, **_: False)
    result = chrome_cdp.ensure_debuggable_chrome(port=9222, launch=False)
    assert result["cdp_url"] is None
    assert result["reason_code"] == "cdp_endpoint_not_available"


def test_missing_executable_reason(monkeypatch):
    monkeypatch.setattr(chrome_cdp, "cdp_endpoint_alive", lambda port, **_: False)
    monkeypatch.setattr(chrome_cdp, "chrome_executable_path", lambda: None)
    result = chrome_cdp.ensure_debuggable_chrome(port=9222)
    assert result["cdp_url"] is None
    assert result["reason_code"] == "chrome_executable_not_found"


def test_launches_and_attaches_when_port_comes_up(monkeypatch, tmp_path):
    fake_exe = tmp_path / "chrome.exe"
    fake_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(chrome_cdp, "chrome_executable_path", lambda: str(fake_exe))
    monkeypatch.setattr(chrome_cdp, "default_user_data_dir", lambda: str(tmp_path / "udd"))

    # Not alive on the first check, then alive after "launch".
    calls = {"n": 0}

    def fake_alive(port, **_):
        calls["n"] += 1
        return calls["n"] > 1

    monkeypatch.setattr(chrome_cdp, "cdp_endpoint_alive", fake_alive)

    launched_args = {}

    def fake_popen(args, **kwargs):
        launched_args["args"] = args
        return object()

    monkeypatch.setattr(chrome_cdp.subprocess, "Popen", fake_popen)

    result = chrome_cdp.ensure_debuggable_chrome(port=9222, profile_directory="Default", wait_seconds=2.0)
    assert result["cdp_url"] == "http://127.0.0.1:9222"
    assert result["launched"] is True and result["reused"] is False
    assert f"--remote-debugging-port=9222" in launched_args["args"]
    assert "--profile-directory=Default" in launched_args["args"]
    assert any(a.startswith("--user-data-dir=") for a in launched_args["args"])


def test_launched_but_port_never_comes_up(monkeypatch, tmp_path):
    fake_exe = tmp_path / "chrome.exe"
    fake_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(chrome_cdp, "chrome_executable_path", lambda: str(fake_exe))
    monkeypatch.setattr(chrome_cdp, "default_user_data_dir", lambda: str(tmp_path / "udd"))
    monkeypatch.setattr(chrome_cdp, "cdp_endpoint_alive", lambda port, **_: False)
    monkeypatch.setattr(chrome_cdp.subprocess, "Popen", lambda args, **kwargs: object())

    result = chrome_cdp.ensure_debuggable_chrome(port=9222, wait_seconds=1.0)
    assert result["cdp_url"] is None
    assert result["launched"] is True
    assert result["reason_code"] == "cdp_endpoint_did_not_start_chrome_already_running"
