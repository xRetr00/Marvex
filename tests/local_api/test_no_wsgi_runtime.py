from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_local_api_runtime_has_no_wsgi_compatibility_surface() -> None:
    runtime_paths = [
        ROOT / "packages" / "local_api",
        ROOT / "services" / "core",
    ]
    forbidden = (
        "wsgiref",
        "WsgiApp",
        "wsgi.input",
        "create_health_version_api_app",
        "WSGIMiddleware",
        "a2wsgi",
        "_call_wsgi_app",
        "core_wsgi_app",
        "control_wsgi_app",
    )

    for root in runtime_paths:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                assert token not in text, f"{path.relative_to(ROOT)} still contains {token}"
