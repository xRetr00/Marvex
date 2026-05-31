from __future__ import annotations

import os
from pathlib import Path

from packages.adapters.capabilities import browser_use, computer_use


def test_chrome_default_profile_is_first_class_browser_use_candidate(monkeypatch, tmp_path: Path) -> None:
    local_app_data = tmp_path / "LocalAppData"
    default_profile = local_app_data / "Google" / "Chrome" / "User Data" / "Default"
    default_profile.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    assert hasattr(browser_use, "chrome_profile_candidates")
    candidates = browser_use.chrome_profile_candidates(preferred_profile="Default")

    assert candidates[0]["mode"] == "system_chrome"
    assert candidates[0]["profile_directory"] == "Default"
    assert candidates[0]["user_data_dir"] == os.path.join(
        str(local_app_data),
        "Google",
        "Chrome",
        "User Data",
    )


def test_windows_mcp_builtin_server_config_defaults_to_local_stdio() -> None:
    assert hasattr(computer_use, "WindowsMcpServerConfig")
    config = computer_use.WindowsMcpServerConfig.builtin()

    assert config.server_id == "windows-mcp"
    assert config.command == "uvx"
    assert config.args == ("windows-mcp", "serve", "--transport", "stdio")
    assert config.transport == "stdio"
    assert config.local_only is True
    assert "PowerShell" in config.destructive_tools
    assert "Registry" in config.destructive_tools
