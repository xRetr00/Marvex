from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_COMPOSITION_ROOT = ROOT / "packages" / "runtime_composition"
CORE_ROOT = ROOT / "packages" / "core"
ASSISTANT_RUNTIME_ROOT = ROOT / "packages" / "assistant_runtime"
PROVIDER_RUNTIME_ROOT = ROOT / "packages" / "provider_runtime"
CLI_ROOT = ROOT / "apps" / "cli"
CLI_MAIN = CLI_ROOT / "main.py"
MANUAL_LOCAL_API_FAKE_TURNS_RUNNER = (
    "packages/runtime_composition/local_api_fake_turns_runner.py"
)
MANUAL_LOCAL_API_LMSTUDIO_TURNS_RUNNER = (
    "packages/runtime_composition/local_api_lmstudio_responses_runner.py"
)
CLI_APPROVED_RUNTIME_COMPOSITION_IMPORTS = {
    "run_fake_provider_assistant_bridge",
    "run_lmstudio_responses_assistant_bridge",
    "run_provider_foundation_turn",
}

ALLOWED_BRIDGE_IMPORT_PREFIXES = (
    "__future__",
    "typing",
    "packages.contracts",
    "packages.core.orchestration",
    "packages.core.orchestration.assistant_provider_stage",
    "packages.provider_runtime",
    "packages.telemetry",
)
MANUAL_LOCAL_API_FAKE_TURNS_RUNNER_IMPORT_PREFIXES = (
    "__future__",
    "argparse",
    "collections.abc",
    "os",
    "packages.local_api.contracts",
    "packages.local_api.runner",
)
BRIDGE_FORBIDDEN_IMPORT_PREFIXES = (
    "packages.adapters",
    "packages.assistant_runtime",
    "packages.ports",
    "apps.cli",
    "services",
)
BRIDGE_FORBIDDEN_TOKENS = (
    "packages.adapters",
    "litellm",
    "lmstudio",
    "openai",
    "openrouter",
    "anthropic",
    "gemini",
    "routing",
    "fallback",
    "retry",
    "session store",
    "session_store",
    "history",
    "api key",
    "api_key",
    "apikey",
    "model selection",
    "model_selection",
    "model router",
    "model_router",
    "tool runtime",
    "memory runtime",
)
APPROVED_REAL_PROVIDER_TOKENS = ("lmstudio_responses",)
APPROVED_LMSTUDIO_LOCAL_API_FILES = {
    "packages/runtime_composition/__init__.py",
    "packages/runtime_composition/assistant_provider_bridge.py",
    "packages/runtime_composition/local_api_lmstudio_responses_runner.py",
    "packages/runtime_composition/local_api_lmstudio_turns.py",
}
APPROVED_LMSTUDIO_TOKEN_PASS_THROUGH_FILES = {
    "packages/runtime_composition/assistant_provider_bridge.py",
    "packages/runtime_composition/local_api_lmstudio_responses_runner.py",
    "packages/runtime_composition/local_api_lmstudio_turns.py",
}
BRIDGE_MAX_LINES = 250
BRIDGE_SIZE_JUSTIFICATION = "runtime composition size justification"


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return None
        return node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _scan_bridge_layer(failures: list[str]) -> None:
    paths = _python_files(RUNTIME_COMPOSITION_ROOT)
    if not paths:
        failures.append("packages/runtime_composition is missing")
        return

    for path in paths:
        rel = _rel(path)
        text = _read(path)
        lowered = text.lower()
        allowed_import_prefixes = ALLOWED_BRIDGE_IMPORT_PREFIXES
        if rel in {
            MANUAL_LOCAL_API_FAKE_TURNS_RUNNER,
            MANUAL_LOCAL_API_LMSTUDIO_TURNS_RUNNER,
        }:
            allowed_import_prefixes = (
                ALLOWED_BRIDGE_IMPORT_PREFIXES
                + MANUAL_LOCAL_API_FAKE_TURNS_RUNNER_IMPORT_PREFIXES
            )
        line_count = len(text.splitlines())
        if (
            line_count > BRIDGE_MAX_LINES
            and BRIDGE_SIZE_JUSTIFICATION not in lowered
        ):
            failures.append(
                f"{rel} has {line_count} lines and exceeds runtime composition max {BRIDGE_MAX_LINES}"
            )
        for token in BRIDGE_FORBIDDEN_TOKENS:
            scanned = lowered
            if token == "lmstudio":
                if rel in APPROVED_LMSTUDIO_LOCAL_API_FILES:
                    scanned = scanned.replace("lmstudio", "")
                else:
                    for allowed in APPROVED_REAL_PROVIDER_TOKENS:
                        scanned = scanned.replace(allowed, "")
            if token in {"api key", "api_key", "apikey"} and rel in (
                APPROVED_LMSTUDIO_TOKEN_PASS_THROUGH_FILES
            ):
                scanned = scanned.replace("marvex_lmstudio_api_key", "")
                scanned = scanned.replace("lmstudio_responses_api_key", "")
            if token in scanned:
                failures.append(f"{rel} contains forbidden bridge behavior token: {token}")

        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            if _matches_prefix(module, BRIDGE_FORBIDDEN_IMPORT_PREFIXES):
                failures.append(f"{rel} imports forbidden dependency: {module}")
            if not _matches_prefix(module, allowed_import_prefixes):
                failures.append(f"{rel} imports non-approved dependency: {module}")


def _scan_layer_mentions(
    *,
    root: Path,
    tokens: tuple[str, ...],
    failures: list[str],
    label: str,
) -> None:
    for path in _python_files(root):
        text = _read(path)
        lowered = text.lower()
        for token in tokens:
            if token.lower() in lowered:
                failures.append(f"{_rel(path)} {label}: {token}")


def _scan_cli_bridge_import(failures: list[str]) -> None:
    for path in _python_files(CLI_ROOT):
        text = _read(path)
        rel = _rel(path)
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            if module == "packages.provider_runtime" or module.startswith(
                "packages.provider_runtime."
            ):
                failures.append(f"{rel} must not import ProviderRuntime directly")
            if module == "packages.adapters" or module.startswith("packages.adapters."):
                failures.append(f"{rel} must not import provider adapters")

        mentions_approved_bridge = any(
            name in text for name in CLI_APPROVED_RUNTIME_COMPOSITION_IMPORTS
        )
        if "packages.runtime_composition" not in text and not mentions_approved_bridge:
            continue
        if path != CLI_MAIN:
            failures.append(f"{rel} must not import runtime composition bridge")
            continue

        allowed_import_seen = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            if module == "packages.runtime_composition":
                imported = {alias.name for alias in node.names}
                if imported == CLI_APPROVED_RUNTIME_COMPOSITION_IMPORTS:
                    allowed_import_seen = True
                    continue
                failures.append(
                    f"{rel} runtime composition import must stay limited to approved CLI bridge functions"
                )
            elif module.startswith("packages.runtime_composition."):
                failures.append(
                    f"{rel} must import runtime composition only through the package root"
                )

        if mentions_approved_bridge and not allowed_import_seen:
            failures.append(
                f"{rel} mentions runtime composition bridge without approved import"
            )


def main() -> int:
    failures: list[str] = []

    _scan_bridge_layer(failures)
    _scan_layer_mentions(
        root=CORE_ROOT,
        tokens=("packages.runtime_composition", "runtime_composition"),
        failures=failures,
        label="must not import or mention runtime composition bridge",
    )
    _scan_layer_mentions(
        root=ASSISTANT_RUNTIME_ROOT,
        tokens=("packages.runtime_composition", "runtime_composition"),
        failures=failures,
        label="must not import or mention runtime composition bridge",
    )
    _scan_layer_mentions(
        root=PROVIDER_RUNTIME_ROOT,
        tokens=("packages.core", "packages.assistant_runtime"),
        failures=failures,
        label="must not import Core or AssistantRuntime",
    )
    _scan_cli_bridge_import(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS runtime composition boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
