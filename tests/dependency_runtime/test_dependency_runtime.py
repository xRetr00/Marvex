"""CI-offline tests for packages/dependency_runtime.

All tests mock importlib.util.find_spec and the pip subprocess so no real
network or pip calls are made.  This validates:
  - missing dep → feature disabled
  - present dep → feature enabled
  - GET /control/deps shape
  - POST /control/deps/install flow (fake pip runner)
  - graceful degrade via unavailable_projection
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.dependency_runtime.detection import (
    DEP_GROUPS,
    DepGroup,
    detect_all,
    detect_dep,
    detect_features,
)
from packages.dependency_runtime.feature_gate import (
    is_feature_available,
    require_feature,
    unavailable_projection,
)
from packages.dependency_runtime.install import (
    InstallRequest,
    InstallResult,
    InstallStatus,
    runtime_install,
)
from tests.control_plane_api.asgi_helpers import asgi_call, create_control_plane_test_app

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Detection tests — mock find_spec so no real packages needed
# ---------------------------------------------------------------------------

def _make_group(id: str, pkgs: tuple[str, ...], feature: str) -> DepGroup:
    return DepGroup(id=id, label=id, feature=feature, packages=pkgs)


def test_missing_dep_gives_installed_false() -> None:
    group = _make_group("stt", ("moonshine",), "stt")
    with patch("importlib.util.find_spec", return_value=None):
        info = detect_dep(group)
    assert info.installed is False
    assert info.feature == "stt"
    assert info.id == "stt"


def test_present_dep_gives_installed_true() -> None:
    group = _make_group("web_search", ("ddgs",), "web_search")
    fake_spec = object()  # truthy non-None value
    with patch("importlib.util.find_spec", return_value=fake_spec):
        info = detect_dep(group)
    assert info.installed is True


def test_detect_all_returns_all_groups() -> None:
    with patch("importlib.util.find_spec", return_value=None):
        infos = detect_all()
    assert len(infos) == len(DEP_GROUPS)
    ids = {info.id for info in infos}
    assert "tts" in ids
    assert "stt" in ids
    assert "wakeword" in ids
    assert "web_search" in ids
    assert "browser" in ids
    assert "mcp" in ids
    assert "computer_use" in ids
    assert "embeddings" in ids


def test_detect_features_all_false_when_no_deps() -> None:
    with patch("importlib.util.find_spec", return_value=None):
        features = detect_features()
    assert features.tts is False
    assert features.stt is False
    assert features.wakeword is False
    assert features.web_search is False
    assert features.browser is False
    assert features.mcp is False
    assert features.computer_use is False
    assert features.embeddings is False


def test_detect_features_web_search_true_when_ddgs_present() -> None:
    def _fake_find_spec(name: str):
        return object() if name == "ddgs" else None

    with patch("importlib.util.find_spec", side_effect=_fake_find_spec):
        features = detect_features()
    assert features.web_search is True
    assert features.tts is False


def test_browser_dep_group_requires_browser_use_and_playwright() -> None:
    def _fake_find_spec(name: str):
        return object() if name == "playwright" else None

    browser_group = next(group for group in DEP_GROUPS if group.id == "browser")
    with patch("importlib.util.find_spec", side_effect=_fake_find_spec):
        info = detect_dep(browser_group)

    assert info.installed is False


def test_mcp_and_computer_use_dep_groups_have_install_specs() -> None:
    groups = {group.id: group for group in DEP_GROUPS}

    assert groups["mcp"].install_specs == ("mcp",)
    assert groups["computer_use"].install_specs == ("mcp", "uiautomation")


def test_funasr_aliyun_transitive_dependency_is_pinned_to_available_wheel() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    assert "aliyun-python-sdk-core-v3==2.13.10" in dependencies

    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    aliyun = next(package for package in lock["package"] if package["name"] == "aliyun-python-sdk-core-v3")
    assert aliyun["version"] == "2.13.10"
    assert "wheels" in aliyun


def test_installer_prebuilds_source_only_hydra_antlr_runtime_wheel() -> None:
    script = (ROOT / "build-installer.ps1").read_text(encoding="utf-8")
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    third_party_source_only = {
        f"{package['name']}=={package['version']}"
        for package in lock["package"]
        if "wheels" not in package and package["name"] != "marvex"
    }

    assert third_party_source_only == {
        "antlr4-python3-runtime==4.9.3",
        "crcmod==1.7",
        "jieba==0.42.1",
        "oss2==2.13.1",
    }
    for requirement in third_party_source_only:
        assert f'Requirement = "{requirement}"' in script
    assert "pip wheel" in script
    assert "--no-binary=:all:" in script
    assert "runtimeDownloadRequirementsFile" in script
    assert "sourceOnlyPackageNames" in script
    assert "--find-links $runtimeWheels" in script


# ---------------------------------------------------------------------------
# Feature gate tests
# ---------------------------------------------------------------------------

def test_require_feature_returns_false_when_missing() -> None:
    with patch("importlib.util.find_spec", return_value=None):
        result = require_feature("tts")
    assert result is False


def test_is_feature_available_returns_true_when_present() -> None:
    def _fake_find_spec(name: str):
        return object() if name in ("supertonic", "piper") else None

    with patch("importlib.util.find_spec", side_effect=_fake_find_spec):
        result = is_feature_available("tts")
    assert result is True


def test_unavailable_projection_shape() -> None:
    proj = unavailable_projection("tts")
    assert proj["status"] == "unavailable"
    assert proj["feature"] == "tts"
    assert proj["raw_payload_persisted"] is False


# ---------------------------------------------------------------------------
# Install tests — fake pip runner (no real pip/network)
# ---------------------------------------------------------------------------

def _fake_pip_ok(argv: list[str]) -> tuple[bool, str]:
    return True, "pip_install_succeeded"


def _fake_pip_fail(argv: list[str]) -> tuple[bool, str]:
    return False, "pip_failed_fake"


def test_install_unknown_dep_returns_blocked() -> None:
    request = InstallRequest(id="nonexistent_dep", explicit_user_triggered=True)
    result = runtime_install(request, pip_runner=_fake_pip_ok)
    assert result.status == InstallStatus.BLOCKED
    assert result.id == "nonexistent_dep"


def test_install_known_dep_triggers_pip_and_returns_installing_when_still_absent() -> None:
    request = InstallRequest(id="embeddings", explicit_user_triggered=True)
    with patch("importlib.util.find_spec", return_value=None):
        result = runtime_install(request, pip_runner=_fake_pip_ok)
    # After fake pip success but find_spec still None → INSTALLING (not yet detectable)
    assert result.status == InstallStatus.INSTALLING
    assert result.id == "embeddings"
    assert result.raw_payload_persisted is False


def test_install_known_dep_with_pip_failure_returns_error() -> None:
    request = InstallRequest(id="embeddings", explicit_user_triggered=True)
    with patch("importlib.util.find_spec", return_value=None):
        result = runtime_install(request, pip_runner=_fake_pip_fail)
    assert result.status == InstallStatus.ERROR
    assert "pip_failed_fake" in result.detail


def test_install_already_installed_returns_installed() -> None:
    request = InstallRequest(id="web_search", explicit_user_triggered=True)
    fake_spec = object()
    with patch("importlib.util.find_spec", return_value=fake_spec):
        result = runtime_install(request, pip_runner=_fake_pip_ok)
    assert result.status == InstallStatus.INSTALLED
    assert result.detail == "already_installed"


def test_install_result_is_safe_projection() -> None:
    request = InstallRequest(id="embeddings", explicit_user_triggered=True)
    with patch("importlib.util.find_spec", return_value=None):
        result = runtime_install(request, pip_runner=_fake_pip_ok)
    serialized = json.dumps(result.model_dump(mode="json"))
    assert "authorization" not in serialized.lower()
    assert result.raw_payload_persisted is False


# ---------------------------------------------------------------------------
# Control plane deps endpoint tests
# ---------------------------------------------------------------------------

def _app_with_deps():
    from packages.control_plane_api import (
        ControlPlaneSnapshot,
        InMemoryApprovalStore,
    )
    store = InMemoryApprovalStore.from_requests(())
    snapshot = ControlPlaneSnapshot.foundation_default(schema_version="1")
    return create_control_plane_test_app(
        approval_store=store,
        snapshot=snapshot,
        local_auth_token="test-token",
        deps_pip_runner=_fake_pip_ok,
    )


def _call(app, path: str, *, method: str = "GET", token: str | None = "test-token", body: dict | None = None):
    status, _headers, payload = asgi_call(app, path, method=method, token=token, body=body)
    return status, payload


def test_get_control_deps_requires_auth() -> None:
    app = _app_with_deps()
    status, payload = _call(app, "/control/deps", token=None)
    assert status == "401 Unauthorized"


def test_get_control_deps_returns_correct_shape() -> None:
    app = _app_with_deps()
    with patch("importlib.util.find_spec", return_value=None):
        status, payload = _call(app, "/control/deps")
    assert status == "200 OK"
    assert "deps" in payload
    assert "features" in payload
    assert payload["raw_payload_persisted"] is False
    # All features absent → all False
    features = payload["features"]
    assert features["tts"] is False
    assert features["stt"] is False
    assert features["web_search"] is False
    # Shape: each dep has id, label, group, installed, feature
    for dep in payload["deps"]:
        assert "id" in dep
        assert "label" in dep
        assert "installed" in dep
        assert "feature" in dep


def test_get_control_deps_shows_web_search_available_when_ddgs_present() -> None:
    app = _app_with_deps()

    def _fake_find_spec(name: str):
        return object() if name == "ddgs" else None

    with patch("importlib.util.find_spec", side_effect=_fake_find_spec):
        status, payload = _call(app, "/control/deps")
    assert status == "200 OK"
    assert payload["features"]["web_search"] is True
    assert payload["features"]["tts"] is False


def test_post_control_deps_install_missing_id_returns_400() -> None:
    app = _app_with_deps()
    status, payload = _call(app, "/control/deps/install", method="POST", body={})
    assert status == "400 Bad Request"


def test_post_control_deps_install_unknown_id_returns_blocked() -> None:
    app = _app_with_deps()
    status, payload = _call(
        app,
        "/control/deps/install",
        method="POST",
        body={"id": "unknown_dep"},
    )
    assert status == "200 OK"
    assert payload["status"] == "blocked"
    assert payload["raw_payload_persisted"] is False


def test_post_control_deps_install_known_dep_triggers_install_flow() -> None:
    app = _app_with_deps()
    with patch("importlib.util.find_spec", return_value=None):
        status, payload = _call(
            app,
            "/control/deps/install",
            method="POST",
            body={"id": "embeddings"},
        )
    assert status == "200 OK"
    assert payload["id"] == "embeddings"
    assert payload["status"] in ("installing", "installed", "error")
    assert payload["raw_payload_persisted"] is False


def test_post_control_deps_install_already_installed_returns_installed() -> None:
    app = _app_with_deps()
    fake_spec = object()
    with patch("importlib.util.find_spec", return_value=fake_spec):
        status, payload = _call(
            app,
            "/control/deps/install",
            method="POST",
            body={"id": "web_search"},
        )
    assert status == "200 OK"
    assert payload["status"] == "installed"


def test_deps_endpoint_no_raw_or_secret_in_response() -> None:
    app = _app_with_deps()
    with patch("importlib.util.find_spec", return_value=None):
        _, payload = _call(app, "/control/deps")
    serialized = json.dumps(payload)
    for forbidden in ("authorization", "bearer", "password", "secret", "api_key"):
        assert forbidden not in serialized.lower()
