from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = ROOT / "packages" / "core"
CLI_ROOT = ROOT / "apps" / "cli"
PORT_ROOT = ROOT / "packages" / "ports" / "provider"
PROVIDER_RUNTIME_ROOT = ROOT / "packages" / "provider_runtime"
PROVIDER_RUNTIME_FILE = PROVIDER_RUNTIME_ROOT / "provider_runtime.py"

PROVIDER_RUNTIME_MAX_LINES = 250
PROVIDER_RUNTIME_SIZE_EXEMPTION = "provider runtime size justification"

CORE_FORBIDDEN = [
    "packages.provider_runtime",
    "packages.adapters",
]

CLI_FORBIDDEN = [
    "packages.adapters.providers.fake",
    "packages.adapters.providers.litellm",
    "packages.adapters.providers.lmstudio_responses",
    "FakeProvider",
    "LiteLLMProvider",
    "LMStudio",
]

PORT_FORBIDDEN = [
    "fake",
    "litellm",
    "lmstudio",
    "openai",
    "openrouter",
    "anthropic",
    "gemini",
]

PROVIDER_RUNTIME_ALLOWED_ADAPTER_IMPORTS = [
    "from packages.adapters.providers.fake import FakeProvider",
    "from packages.adapters.providers.litellm import LiteLLMProvider",
    "from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider",
]
PROVIDER_RUNTIME_ALLOWED_ADAPTER_NAMES = {
    "FakeProvider",
    "LiteLLMProvider",
    "LMStudioResponsesProvider",
}

PROVIDER_RUNTIME_FORBIDDEN_IMPORTS = [
    re.compile(
        r"^\s*from\s+packages\.adapters\.providers\.(?!fake\b|litellm\b|lmstudio_responses\b)"
    ),
    re.compile(
        r"^\s*import\s+packages\.adapters\.providers\.(?!fake\b|litellm\b|lmstudio_responses\b)"
    ),
]
PROVIDER_RUNTIME_AGGREGATE_IMPORT = re.compile(
    r"^\s*from\s+packages\.adapters\.providers\s+import\s+(.+)$"
)

PROVIDER_RUNTIME_FORBIDDEN_TOKENS = [
    "fallback",
    "retry",
    "session",
    "history",
    "plugin",
    "daemon",
    "server",
    "health routing",
    "health_routing",
    "health-route",
    "health route",
    "model routing",
    "model_routing",
    "model-route",
    "model route",
]


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _scan_for_tokens(
    *,
    paths: list[Path],
    tokens: list[str],
    failures: list[str],
    label: str,
    case_sensitive: bool = True,
) -> None:
    for path in paths:
        text = _read_text(path)
        if text is None:
            continue
        scanned_text = text if case_sensitive else text.lower()
        scanned_tokens = tokens if case_sensitive else [token.lower() for token in tokens]
        for token, scanned_token in zip(tokens, scanned_tokens):
            if scanned_token in scanned_text:
                failures.append(f"{_rel(path)} {label}: {token}")


def _scan_core(failures: list[str]) -> None:
    _scan_for_tokens(
        paths=_python_files(CORE_ROOT),
        tokens=CORE_FORBIDDEN,
        failures=failures,
        label="must not mention provider runtime or adapters",
    )


def _scan_cli(failures: list[str]) -> None:
    _scan_for_tokens(
        paths=_python_files(CLI_ROOT),
        tokens=CLI_FORBIDDEN,
        failures=failures,
        label="must not mention concrete provider adapters",
    )


def _scan_provider_port(failures: list[str]) -> None:
    _scan_for_tokens(
        paths=_python_files(PORT_ROOT),
        tokens=PORT_FORBIDDEN,
        failures=failures,
        label="must remain provider-agnostic",
        case_sensitive=False,
    )


def _scan_provider_runtime(failures: list[str]) -> None:
    runtime_paths = _python_files(PROVIDER_RUNTIME_ROOT)
    _scan_for_tokens(
        paths=runtime_paths,
        tokens=PROVIDER_RUNTIME_FORBIDDEN_TOKENS,
        failures=failures,
        label="must not contain runtime expansion logic",
        case_sensitive=False,
    )

    for path in runtime_paths:
        text = _read_text(path)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in PROVIDER_RUNTIME_FORBIDDEN_IMPORTS):
                failures.append(
                    f"{_rel(path)}:{line_number} imports unapproved provider adapter"
                )
            aggregate_import = PROVIDER_RUNTIME_AGGREGATE_IMPORT.search(line)
            if aggregate_import:
                imported_names = [
                    name.strip().split(" as ", 1)[0].strip()
                    for name in aggregate_import.group(1).split(",")
                ]
                for name in imported_names:
                    if name not in PROVIDER_RUNTIME_ALLOWED_ADAPTER_NAMES:
                        failures.append(
                            f"{_rel(path)}:{line_number} imports unapproved provider adapter name: {name}"
                        )
            if "packages.adapters.providers." in line:
                if line.strip() not in PROVIDER_RUNTIME_ALLOWED_ADAPTER_IMPORTS:
                    failures.append(
                        f"{_rel(path)}:{line_number} provider runtime adapter import must be explicitly approved"
                    )

    if PROVIDER_RUNTIME_FILE.is_file():
        text = _read_text(PROVIDER_RUNTIME_FILE)
        if text is not None:
            line_count = len(text.splitlines())
            if (
                line_count > PROVIDER_RUNTIME_MAX_LINES
                and PROVIDER_RUNTIME_SIZE_EXEMPTION not in text.lower()
            ):
                failures.append(
                    f"{_rel(PROVIDER_RUNTIME_FILE)} has {line_count} lines and exceeds provider runtime max {PROVIDER_RUNTIME_MAX_LINES}"
                )


def main() -> int:
    failures: list[str] = []

    _scan_core(failures)
    _scan_cli(failures)
    _scan_provider_port(failures)
    _scan_provider_runtime(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS provider runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
