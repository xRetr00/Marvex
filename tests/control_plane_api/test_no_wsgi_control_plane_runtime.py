from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_control_plane_runtime_has_no_wsgi_compatibility_surface() -> None:
    forbidden = (
        "wsgiref",
        "WsgiApp",
        "wsgi.input",
        "create_control_plane_api_app",
        "WSGIMiddleware",
        "a2wsgi",
        "_call_wsgi_app",
        "control_wsgi_app",
    )

    for path in (ROOT / "packages" / "control_plane_api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.relative_to(ROOT)} still contains {token}"
