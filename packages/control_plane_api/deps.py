"""Control-plane deps endpoints: GET /control/deps and POST /control/deps/install.

Both endpoints are:
- Bearer-auth protected (handled by caller in app.py)
- Loopback-only in production (network policy enforced by the server binding)
- Safe-projection only: no raw payloads, no credentials, no shell strings
- Explicit/user-initiated installs only
"""
from __future__ import annotations

from typing import Any

from packages.dependency_runtime.detection import detect_all, detect_features
from packages.dependency_runtime.install import InstallRequest, InstallStatus, runtime_install

from .voice import _read_json

SCHEMA_VERSION = "1"
CONTROL_DEPS_PREFIX = "/control/deps"


def handle_deps_request(
    *,
    method: str,
    path: str,
    environ: dict[str, Any],
    pip_runner: Any | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Route /control/deps GET and /control/deps/install POST.

    Returns (status, payload) or None if path not matched.
    """
    if not path.startswith(CONTROL_DEPS_PREFIX):
        return None

    if method == "GET" and path == CONTROL_DEPS_PREFIX:
        return _handle_deps_list()

    if method == "POST" and path == f"{CONTROL_DEPS_PREFIX}/install":
        body = _read_json(environ)
        return _handle_deps_install(body, pip_runner=pip_runner)

    return None


def _handle_deps_list() -> tuple[str, dict[str, Any]]:
    dep_infos = detect_all()
    features = detect_features()
    return "200 OK", {
        "schema_version": SCHEMA_VERSION,
        "deps": [
            {
                "id": info.id,
                "label": info.label,
                "group": info.group,
                "installed": info.installed,
                "feature": info.feature,
            }
            for info in dep_infos
        ],
        "features": features.model_dump(mode="json"),
        "raw_payload_persisted": False,
    }


def _handle_deps_install(
    body: dict[str, Any],
    *,
    pip_runner: Any | None = None,
) -> tuple[str, dict[str, Any]]:
    dep_id = str(body.get("id") or "").strip()
    if not dep_id:
        return "400 Bad Request", {
            "schema_version": SCHEMA_VERSION,
            "error": "missing_dep_id",
            "message": "Field 'id' is required.",
            "raw_payload_persisted": False,
        }
    try:
        request = InstallRequest(id=dep_id, explicit_user_triggered=True)
    except Exception as exc:  # noqa: BLE001
        return "400 Bad Request", {
            "schema_version": SCHEMA_VERSION,
            "error": "invalid_request",
            "message": str(exc)[:300],
            "raw_payload_persisted": False,
        }
    result = runtime_install(request, pip_runner=pip_runner)
    http_status = "200 OK" if result.status != InstallStatus.ERROR else "500 Internal Server Error"
    return http_status, {
        "schema_version": SCHEMA_VERSION,
        "id": result.id,
        "status": result.status.value,
        "detail": result.detail,
        "raw_payload_persisted": False,
    }


