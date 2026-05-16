from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT_ROOT = ROOT / "packages" / "local_api_client"

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "collections.abc",
    "dataclasses",
    "json",
    "packages.local_service_startup.discovery",
    "pathlib",
    "typing",
    "urllib.error",
    "urllib.request",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "apps",
    "packages.adapters",
    "packages.assistant_runtime",
    "packages.core",
    "packages.local_api",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.telemetry",
    "services",
)
FORBIDDEN_SOURCE_TOKENS = (
    "websocket",
    "daemon",
    "supervisor",
    "auto_restart",
    "session_store",
    "history",
    "retry",
    "fallback",
    "model selection",
    "model_selection",
    "model_selector",
    "routing",
    "create_provider",
    "run_lmstudio_responses_assistant_bridge",
    "run_fake_provider_assistant_bridge",
    "providerrequest",
    "providerresponse",
    "memory runtime",
    "tool runtime",
    "voice",
    "desktop",
    "vision",
    "proactive",
)


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


def _assignment_target_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    targets: list[ast.expr]
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    else:
        targets = [node.target]

    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        if isinstance(target, ast.Attribute):
            names.append(target.attr)
    return names


def _scan_token_storage(rel: str, tree: ast.AST, failures: list[str]) -> None:
    allowed_token_presence_names = {"auth_token_present"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        for name in _assignment_target_names(node):
            if name in allowed_token_presence_names:
                continue
            lowered = name.lower()
            if "token" in lowered or "secret" in lowered:
                failures.append(f"{rel} stores token/secret material")


def _scan_client_boundaries(failures: list[str]) -> None:
    paths = _python_files(CLIENT_ROOT)
    if not paths:
        failures.append("packages/local_api_client is missing")
        return

    for path in paths:
        rel = _rel(path)
        text = _read(path)
        lowered = text.lower()
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in lowered:
                failures.append(f"{rel} contains forbidden client behavior token: {token}")

        tree = ast.parse(text, filename=str(path))
        _scan_token_storage(rel, tree, failures)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            if _matches_prefix(module, FORBIDDEN_IMPORT_PREFIXES):
                failures.append(f"{rel} imports forbidden dependency: {module}")
            if not _matches_prefix(module, ALLOWED_IMPORT_PREFIXES):
                failures.append(f"{rel} imports non-approved dependency: {module}")


def main() -> int:
    failures: list[str] = []
    _scan_client_boundaries(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS local API client boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
