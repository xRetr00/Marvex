from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_SCHEMA_VERSION = "0.1.1-draft"
DEPRECATED_SCHEMA_VERSION = "0.1-draft"
ALLOWED_DEPRECATED_REFERENCES = {
    "docs/SCHEMA_VERSION_POLICY.md",
    "scripts/check_schema_versions.py",
}
TEXT_SUFFIXES = {".md", ".py", ".toml"}
SCAN_ROOTS = [
    "README.md",
    "PROJECT_STATUS.md",
    "docs",
    "packages",
    "tests",
    "scripts",
    "templates",
]


def _iter_text_files() -> list[Path]:
    paths: list[Path] = []
    for rel in SCAN_ROOTS:
        path = ROOT / rel
        if path.is_file():
            paths.append(path)
            continue
        if path.is_dir():
            paths.extend(
                child
                for child in path.rglob("*")
                if child.is_file() and child.suffix.lower() in TEXT_SUFFIXES
            )
    return sorted(set(paths))


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    failures: list[str] = []

    policy = ROOT / "docs" / "SCHEMA_VERSION_POLICY.md"
    if not policy.is_file():
        failures.append("missing docs/SCHEMA_VERSION_POLICY.md")
    else:
        text = policy.read_text(encoding="utf-8")
        if f"active v1 Provider Foundation schema version is `{ACTIVE_SCHEMA_VERSION}`" not in text:
            failures.append(
                f"docs/SCHEMA_VERSION_POLICY.md must declare active schema version {ACTIVE_SCHEMA_VERSION}"
            )
        if f"`{DEPRECATED_SCHEMA_VERSION}` is deprecated" not in text:
            failures.append(
                f"docs/SCHEMA_VERSION_POLICY.md must declare {DEPRECATED_SCHEMA_VERSION} deprecated"
            )

    for path in _iter_text_files():
        rel = _rel(path)
        text = path.read_text(encoding="utf-8")
        if DEPRECATED_SCHEMA_VERSION in text and rel not in ALLOWED_DEPRECATED_REFERENCES:
            failures.append(
                f"{rel} contains deprecated active schema version reference: {DEPRECATED_SCHEMA_VERSION}"
            )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS schema version policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
