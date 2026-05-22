from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_ROOT = ROOT / "apps" / "cli"
CORE_ROOT = ROOT / "packages" / "core"
PORTS_ROOT = ROOT / "packages" / "ports"
DECISION_RUNTIME_ROOT = ROOT / "packages" / "decision_runtime"
ADAPTERS_ROOT = ROOT / "packages" / "adapters"

CLI_FORBIDDEN_IMPORTS = (
    "packages.decision_runtime",
    "packages.adapters",
)
CORE_FORBIDDEN_IMPORTS = (
    "packages.decision_runtime",
    "packages.adapters",
)
PORT_ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "typing",
    "collections.abc",
    "packages.contracts",
)
FACTORY_FORBIDDEN_NAME_PARTS = (
    "dev",
    "payload",
    "summary",
    "report",
)
FACTORY_FORBIDDEN_CALLS = (
    "model_dump",
    "model_dump_json",
    "dump",
    "dumps",
)
FINAL_ACTION_ALLOWED = {
    "packages/adapters/pipeline/decision_pipeline.py",
}


def _read_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return None
        return node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _iter_py(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob("*.py"))


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _import_violates(module: str | None, forbidden: tuple[str, ...]) -> bool:
    return module is not None and any(
        module == item or module.startswith(f"{item}.") for item in forbidden
    )


def _scan_cli_imports(failures: list[str]) -> None:
    for path in _iter_py(CLI_ROOT):
        for node in ast.walk(_read_tree(path)):
            if isinstance(node, ast.Import | ast.ImportFrom) and _import_violates(
                _module_from_import(node),
                CLI_FORBIDDEN_IMPORTS,
            ):
                failures.append(f"{_rel(path)} imports decision/adapters boundary")


def _scan_core_imports(failures: list[str]) -> None:
    for path in _iter_py(CORE_ROOT):
        for node in ast.walk(_read_tree(path)):
            if isinstance(node, ast.Import | ast.ImportFrom) and _import_violates(
                _module_from_import(node),
                CORE_FORBIDDEN_IMPORTS,
            ):
                failures.append(f"{_rel(path)} imports decision/adapters boundary")


def _scan_ports_imports(failures: list[str]) -> None:
    for path in _iter_py(PORTS_ROOT):
        for node in ast.walk(_read_tree(path)):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            if not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in PORT_ALLOWED_IMPORT_PREFIXES
            ):
                failures.append(f"{_rel(path)} imports non-contract module: {module}")


def _scan_factories(failures: list[str]) -> None:
    for path in _iter_py(DECISION_RUNTIME_ROOT):
        if "factory" not in path.name:
            continue
        tree = _read_tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                failures.append(f"{_rel(path)} defines class {node.name}")
            if isinstance(node, ast.FunctionDef):
                lowered = node.name.lower()
                if lowered.startswith("run_") or any(
                    part in lowered for part in FACTORY_FORBIDDEN_NAME_PARTS
                ):
                    failures.append(f"{_rel(path)} defines non-composition function {node.name}")
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name in FACTORY_FORBIDDEN_CALLS:
                    failures.append(f"{_rel(path)} performs payload/report shaping call: {name}")
            if isinstance(node, ast.Name) and node.id.lower().startswith("_dev"):
                failures.append(f"{_rel(path)} references dev component {node.id}")


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _scan_final_action_authority(failures: list[str]) -> None:
    for path in _iter_py(ADAPTERS_ROOT):
        rel = _rel(path)
        if rel in FINAL_ACTION_ALLOWED:
            continue
        tree = _read_tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "packages.contracts.decision_pipeline_models":
                imported = {alias.name for alias in node.names}
                if "DecisionFinalAction" in imported:
                    failures.append(f"{rel} imports DecisionFinalAction outside pipeline authority")


def main() -> int:
    failures: list[str] = []
    _scan_cli_imports(failures)
    _scan_core_imports(failures)
    _scan_ports_imports(failures)
    _scan_factories(failures)
    _scan_final_action_authority(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS decision runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
