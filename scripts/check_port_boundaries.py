from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTS_ROOT = ROOT / "packages" / "ports"
ADAPTERS_ROOT = ROOT / "packages" / "adapters"
CORE_ROOT = ROOT / "packages" / "core"

PORT_MAX_LINES = 120
REGISTRY_FACTORY_MAX_LINES = 250
PORT_SIZE_JUSTIFICATION = "port size justification"
REGISTRY_FACTORY_JUSTIFICATION = "registry/factory size justification"
EXCLUDED_PARTS = {"node_modules", "dist", ".venv"}

CONCRETE_NAME_PATTERNS = [
    r"\blitellm\b",
    r"\blm\s*studio\b",
    r"\blmstudio\b",
    r"\bopenai\b",
    r"\bopenrouter\b",
    r"\banthropic\b",
    r"\bgemini\b",
    r"\bfakeprovider\b",
    r"\blmstudioresponsesadapter\b",
    r"\blitellmadapter\b",
]

ADAPTER_IMPORTS_CORE = [
    re.compile(r"^\s*from\s+packages\.core(\.|\s|$)", re.IGNORECASE),
    re.compile(r"^\s*import\s+packages\.core(\.|\s|$)", re.IGNORECASE),
]

CORE_IMPORTS_ADAPTERS = [
    re.compile(r"^\s*from\s+packages\.adapters(\.|\s|$)", re.IGNORECASE),
    re.compile(r"^\s*import\s+packages\.adapters(\.|\s|$)", re.IGNORECASE),
]


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _scan_port_files(failures: list[str]) -> None:
    if not PORTS_ROOT.exists():
        return

    for path in PORTS_ROOT.rglob("*.py"):
        text = _read_text(path)
        if text is None:
            continue

        rel = path.relative_to(ROOT).as_posix()
        line_count = len(text.splitlines())
        if line_count > PORT_MAX_LINES and PORT_SIZE_JUSTIFICATION not in text.lower():
            failures.append(
                f"{rel} has {line_count} lines and exceeds port max {PORT_MAX_LINES} without justification"
            )

        lowered = text.lower()
        for pattern in CONCRETE_NAME_PATTERNS:
            if re.search(pattern, lowered):
                failures.append(f"{rel} mentions concrete implementation name matching pattern: {pattern}")


def _scan_adapter_import_direction(failures: list[str]) -> None:
    if not ADAPTERS_ROOT.exists():
        return

    for path in ADAPTERS_ROOT.rglob("*.py"):
        text = _read_text(path)
        if text is None:
            continue

        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in ADAPTER_IMPORTS_CORE):
                failures.append(f"{rel}:{lineno} adapter imports core")


def _scan_core_import_direction(failures: list[str]) -> None:
    if not CORE_ROOT.exists():
        return

    for path in CORE_ROOT.rglob("*.py"):
        text = _read_text(path)
        if text is None:
            continue

        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in CORE_IMPORTS_ADAPTERS):
                failures.append(f"{rel}:{lineno} core imports adapters")


def _scan_registry_factory_sizes(failures: list[str]) -> None:
    for path in ROOT.rglob("*.py"):
        if any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        name = path.name.lower()
        if "registry" not in name and "factory" not in name:
            continue

        text = _read_text(path)
        if text is None:
            continue

        line_count = len(text.splitlines())
        if line_count <= REGISTRY_FACTORY_MAX_LINES:
            continue

        if REGISTRY_FACTORY_JUSTIFICATION in text.lower():
            continue

        rel = path.relative_to(ROOT).as_posix()
        failures.append(
            f"{rel} has {line_count} lines and exceeds registry/factory max {REGISTRY_FACTORY_MAX_LINES}"
        )


def main() -> int:
    failures: list[str] = []

    _scan_port_files(failures)
    _scan_adapter_import_direction(failures)
    _scan_core_import_direction(failures)
    _scan_registry_factory_sizes(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS port boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
