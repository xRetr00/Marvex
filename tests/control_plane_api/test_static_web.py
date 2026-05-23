from pathlib import Path

from packages.control_plane_api.static_web import resolve_static_file


def test_resolves_index_for_root(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>marvex</html>", encoding="utf-8")
    resolved, content_type = resolve_static_file(tmp_path, "/")
    assert resolved == (tmp_path / "index.html").resolve()
    assert content_type == "text/html; charset=utf-8"


def test_resolves_asset(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("//", encoding="utf-8")
    resolved, content_type = resolve_static_file(tmp_path, "/assets/app.js")
    assert resolved == (assets / "app.js").resolve()
    assert content_type == "application/javascript"


def test_spa_fallback_to_index(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    resolved, _ = resolve_static_file(tmp_path, "/some/spa/route")
    assert resolved == (tmp_path / "index.html").resolve()


def test_blocks_path_traversal(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    resolved, _ = resolve_static_file(tmp_path, "/../secret")
    # Traversal must never escape the dist root; falls back to index.
    assert resolved == (tmp_path / "index.html").resolve()
