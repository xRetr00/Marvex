from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_RUNTIME = ROOT / "packages" / "capability_runtime"
ADAPTERS = ROOT / "packages" / "adapters" / "capabilities"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

SDK_ALLOWED_FILES = {
    ADAPTERS / "browser.py": ("playwright",),
    ADAPTERS / "browser_use.py": ("browser_use",),
}
SDK_FORBIDDEN_NON_OWNER = ("playwright", "browser_use", "agents")
SDK_FORBIDDEN_ADAPTERS = ()
NON_OWNER_ROOTS = (
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "assistant_runtime",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "telemetry",
    ROOT / "packages" / "memory_runtime",
    ROOT / "packages" / "session_runtime",
    ROOT / "packages" / "local_service_startup",
)
FORBIDDEN_TEXT = (
    "credential_entry_allowed: Literal[True]",
    "captcha_or_antibot_bypass_allowed: Literal[True]",
    "agents_sdk_owns_execution: Literal[True]",
)
REQUIRED_RUNTIME_TEXT = (
    "ToolRiskLevel",
    "ToolSideEffectLevel",
    "ApprovalPrompt",
    "ApprovalDecision",
    "CapabilityExecutionMode",
    "ToolExecutionPolicy",
    "ToolingTelemetrySummary",
    "CapabilityToolContextDelivery",
)
REQUIRED_ADAPTER_FILES = (
    "builtins.py",
    "browser.py",
    "browser_use.py",
    "computer_use.py",
    "openai_computer_use.py",
    "openai_agents.py",
)
REQUIRED_DOC_PHRASES = (
    "Full Tooling and Computer Use Foundation",
    "CapabilityRuntime remains authoritative",
    "Playwright",
    "Browser-use backend runs in personal owner mode",
    "OpenAI Agents SDK cannot own the Marvex agent loop",
    "OpenAI Computer Use",
)


def _python_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.py") if path.is_file()) if root.exists() else []


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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


def main() -> int:
    failures: list[str] = []
    runtime_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(CAPABILITY_RUNTIME))
    adapter_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(ADAPTERS))

    for phrase in REQUIRED_RUNTIME_TEXT:
        if phrase not in runtime_text:
            failures.append(f"CapabilityRuntime missing tooling policy phrase: {phrase}")

    for filename in REQUIRED_ADAPTER_FILES:
        if not (ADAPTERS / filename).is_file():
            failures.append(f"missing tooling adapter foundation file: packages/adapters/capabilities/{filename}")

    for root in (CAPABILITY_RUNTIME, ADAPTERS):
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_TEXT:
                if token in text:
                    failures.append(f"{_rel(path)} contains forbidden tooling token: {token}")

    for path in _python_files(ADAPTERS):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = _module_from_import(node)
            if module and _matches_prefix(module, SDK_FORBIDDEN_ADAPTERS):
                failures.append(f"{_rel(path)} imports blocked browser-use SDK dependency: {module}")

    for root in NON_OWNER_ROOTS:
        for path in _python_files(root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = _module_from_import(node)
                if module and _matches_prefix(module, SDK_FORBIDDEN_NON_OWNER):
                    failures.append(f"{_rel(path)} imports forbidden tooling SDK dependency: {module}")
            text = path.read_text(encoding="utf-8")
            if "BrowserActionProposal" in text or "ComputerUseActionProposal" in text:
                failures.append(f"{_rel(path)} must not own browser/computer tool proposals")

    for path, allowed_modules in SDK_ALLOWED_FILES.items():
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = {_module_from_import(node) for node in ast.walk(tree)}
        for module in allowed_modules:
            if not any(imported_module and _matches_prefix(imported_module, (module,)) for imported_module in imported):
                failures.append(f"{_rel(path)} must import SDK boundary: {module}")

    if "playwright==1.60.0" not in (ROOT / "pyproject.toml").read_text(encoding="utf-8"):
        failures.append("pyproject.toml must declare playwright==1.60.0")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if "browser-use==0.11.13" not in pyproject:
        failures.append("pyproject.toml must declare browser-use==0.11.13 as a disabled adapter backend")
    if "openai-agents==0.17.2" not in pyproject:
        failures.append("pyproject.toml must declare openai-agents==0.17.2")
    if "check_full_tooling_boundaries.py" not in RUN_ALL_CHECKS.read_text(encoding="utf-8"):
        failures.append("scripts/run_all_checks.py must run check_full_tooling_boundaries.py")

    docs = VALIDATION_GATES.read_text(encoding="utf-8") + "\n" + PROJECT_STATUS.read_text(encoding="utf-8")
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"tooling docs/status missing phrase: {phrase}")

    if "packages.capability_runtime" not in adapter_text:
        failures.append("tooling adapters must use CapabilityRuntime models")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS full tooling boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
