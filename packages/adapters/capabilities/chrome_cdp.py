"""Ensure a Chrome instance is running with its DevTools/CDP endpoint enabled,
pointed at the user's REAL profile, so browser automation drives the user's
actual browser + logins instead of a throwaway Playwright/automation profile.

This is the fix for "the browser opened but not my main profile, showed a
Playwright page, then closed": browser_use's launch fell back to a dedicated
profile and closed on completion. Instead we (re)launch the user's own Chrome
with ``--remote-debugging-port`` on their User Data dir and connect over CDP,
with ``keep_alive`` so the window is never auto-closed.

Stdlib only - this module must NOT import browser_use/playwright/agents (tooling
boundary gate). The SDK clients connect to the ``cdp_url`` this returns.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

DEFAULT_CDP_PORT = 9222


def chrome_cdp_port() -> int:
    raw = os.environ.get("MARVEX_CHROME_CDP_PORT", "").strip()
    if raw.isdigit():
        port = int(raw)
        if 1 <= port <= 65535:
            return port
    return DEFAULT_CDP_PORT


def chrome_executable_path() -> str | None:
    """Locate a Chrome/Chromium executable (env override wins)."""

    override = os.environ.get("MARVEX_CHROME_PATH", "").strip()
    if override and Path(override).exists():
        return override

    candidates: list[Path] = []
    if sys.platform.startswith("win"):
        for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env_name)
            if base:
                candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
        candidates.append(Path("/Applications/Chromium.app/Contents/MacOS/Chromium"))
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))
    for name in ("chrome", "chrome.exe", "google-chrome"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    for candidate in candidates:
        try:
            if candidate and candidate.exists():
                return str(candidate)
        except OSError:
            continue
    return None


def default_user_data_dir() -> str | None:
    """The user's real Chrome User Data dir (env override wins)."""

    override = os.environ.get("MARVEX_CHROME_USER_DATA_DIR", "").strip()
    if override:
        return override
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return str(Path(base) / "Google" / "Chrome" / "User Data")
    elif sys.platform == "darwin":
        return str(Path.home() / "Library" / "Application Support" / "Google" / "Chrome")
    else:
        return str(Path.home() / ".config" / "google-chrome")
    return None


def fallback_user_data_dir() -> str:
    """Dedicated Marvex Chrome profile used when the real profile is locked.

    Chrome cannot add ``--remote-debugging-port`` to an already-running process
    that owns the user's normal profile. This profile keeps automation live
    instead of failing, while preserving the first-choice path of attaching to
    the user's real Chrome whenever possible.
    """

    override = os.environ.get("MARVEX_BROWSER_PROFILE_DIR", "").strip()
    if override:
        return override
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return str(Path(base) / "com.marvex.shell" / "chrome-cdp-profile")
    return str(Path.home() / ".marvex-automation" / "chrome-cdp-profile")


def cdp_endpoint_alive(port: int, *, timeout: float = 0.5) -> bool:
    """True when a Chrome DevTools endpoint is already listening on ``port``."""

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            pass
    except OSError:
        return False
    try:
        with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=timeout) as response:
            body = response.read().decode("utf-8", "ignore") or "{}"
        data = json.loads(body)
        return isinstance(data, dict) and ("webSocketDebuggerUrl" in data or "Browser" in data)
    except Exception:
        return False


def ensure_debuggable_chrome(
    *,
    port: int | None = None,
    user_data_dir: str | None = None,
    profile_directory: str = "Default",
    launch: bool = True,
    wait_seconds: float = 12.0,
) -> dict[str, object]:
    """Return a CDP url for the user's Chrome, launching it with the debug port
    on their real profile if one isn't already listening.

    Result dict: ``cdp_url`` (str|None), ``port``, ``launched`` (bool),
    ``reused`` (bool), ``reason_code`` (str|None). ``cdp_url`` is None on failure
    with a precise ``reason_code`` the adapter surfaces to the user.
    """

    resolved_port = port or chrome_cdp_port()
    cdp_url = f"http://127.0.0.1:{resolved_port}"

    if cdp_endpoint_alive(resolved_port):
        return {"cdp_url": cdp_url, "port": resolved_port, "launched": False, "reused": True, "reason_code": None}
    if not launch:
        return {"cdp_url": None, "port": resolved_port, "launched": False, "reused": False, "reason_code": "cdp_endpoint_not_available"}

    executable = chrome_executable_path()
    if not executable:
        return {"cdp_url": None, "port": resolved_port, "launched": False, "reused": False, "reason_code": "chrome_executable_not_found"}

    resolved_user_data_dir = user_data_dir or default_user_data_dir()
    args = [
        executable,
        f"--remote-debugging-port={resolved_port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--restore-last-session",
    ]
    if resolved_user_data_dir:
        try:
            Path(resolved_user_data_dir).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        args.append(f"--user-data-dir={resolved_user_data_dir}")
    if profile_directory:
        args.append(f"--profile-directory={profile_directory}")

    try:
        subprocess.Popen(  # noqa: S603 - launching the user's own Chrome by absolute path
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception as exc:
        return {
            "cdp_url": None,
            "port": resolved_port,
            "launched": False,
            "reused": False,
            "reason_code": f"chrome_launch_failed:{type(exc).__name__}",
        }

    deadline = time.monotonic() + max(1.0, wait_seconds)
    while time.monotonic() < deadline:
        if cdp_endpoint_alive(resolved_port):
            return {"cdp_url": cdp_url, "port": resolved_port, "launched": True, "reused": False, "reason_code": None}
        time.sleep(0.3)

    fallback_enabled = (
        os.environ.get("MARVEX_CHROME_CDP_ALLOW_FALLBACK", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    fallback_disabled = (
        os.environ.get("MARVEX_CHROME_CDP_NO_FALLBACK", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    fallback_dir = fallback_user_data_dir()
    if (
        fallback_enabled
        and not fallback_disabled
        and fallback_dir
        and str(Path(fallback_dir)) != str(Path(resolved_user_data_dir or ""))
    ):
        fallback_args = [
            executable,
            f"--remote-debugging-port={resolved_port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--restore-last-session",
        ]
        try:
            Path(fallback_dir).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        fallback_args.append(f"--user-data-dir={fallback_dir}")
        if profile_directory:
            fallback_args.append(f"--profile-directory={profile_directory}")
        try:
            subprocess.Popen(  # noqa: S603 - launching Chrome by absolute path
                fallback_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception as exc:
            return {
                "cdp_url": None,
                "port": resolved_port,
                "launched": True,
                "reused": False,
                "fallback_profile": True,
                "reason_code": f"chrome_fallback_launch_failed:{type(exc).__name__}",
            }
        fallback_deadline = time.monotonic() + max(1.0, wait_seconds)
        while time.monotonic() < fallback_deadline:
            if cdp_endpoint_alive(resolved_port):
                return {
                    "cdp_url": cdp_url,
                    "port": resolved_port,
                    "launched": True,
                    "reused": False,
                    "fallback_profile": True,
                    "reason_code": None,
                }
            time.sleep(0.3)
        return {
            "cdp_url": None,
            "port": resolved_port,
            "launched": True,
            "reused": False,
            "fallback_profile": True,
            "reason_code": "cdp_endpoint_did_not_start_after_fallback_profile",
        }

    # Launched but the debug port never came up. The dominant cause on Windows is
    # that a Chrome was ALREADY running on this user-data-dir without the debug
    # flag, so our invocation just opened a tab in it and exited (Chrome only
    # enables remote debugging for the first process owning a profile dir).
    return {
        "cdp_url": None,
        "port": resolved_port,
        "launched": True,
        "reused": False,
        "reason_code": "cdp_endpoint_did_not_start_chrome_already_running",
    }


__all__ = [
    "DEFAULT_CDP_PORT",
    "chrome_cdp_port",
    "chrome_executable_path",
    "default_user_data_dir",
    "fallback_user_data_dir",
    "cdp_endpoint_alive",
    "ensure_debuggable_chrome",
]
