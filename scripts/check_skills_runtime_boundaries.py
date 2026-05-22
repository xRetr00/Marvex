from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_RUNTIME = ROOT / "packages" / "skills_runtime"
SKILL_ADAPTER = ROOT / "packages" / "adapters" / "capabilities" / "skills.py"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"
NON_OWNER_ROOTS = (
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "local_service_startup",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "telemetry",
    ROOT / "packages" / "assistant_runtime",
    ROOT / "packages" / "memory_runtime",
    ROOT / "packages" / "session_runtime",
    ROOT / "packages" / "adapters" / "capabilities" / "mcp.py",
)

ALLOWED_IMPORTS = (
    "__future__",
    "enum",
    "packages.capability_runtime",
    "packages.skills_runtime",
    "pathlib",
    "pydantic",
    "re",
    "typing",
)
FORBIDDEN_IMPORTS = (
    "apps",
    "os",
    "subprocess",
    "requests",
    "httpx",
    "socket",
    "webbrowser",
    "packages.core",
    "packages.local_api",
    "packages.local_service_startup",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.telemetry",
    "packages.assistant_runtime",
    "packages.memory_runtime",
    "packages.session_runtime",
    "packages.adapters.capabilities.mcp",
    "services",
)
FORBIDDEN_TEXT = (
    "exec(",
    "eval(",
    "subprocess",
    "pip install",
    "git clone",
    "http://",
    "https://",
    "raw_prompt_persisted=True",
    "raw_transcript_persisted=True",
    "arbitrary_script_execution_allowed: Literal[True]",
    "can_override_system_policy: Literal[True]",
    "remote_loading_allowed: Literal[True]",
)
REQUIRED_TEXT = (
    "SkillManifest",
    "SkillValidationResult",
    "SkillEligibilityDecision",
    "SkillPromptContribution",
    "SkillResourceRef",
    "SafeSkillProjection",
    "CapabilityContextPack",
    "can_override_system_policy: Literal[False]",
    "arbitrary_script_execution_allowed: Literal[False]",
    "remote_loading_allowed: Literal[False]",
)
REQUIRED_DOC_PHRASES = (
    "Skills Runtime Foundation",
    "Skill is bounded capability context",
    "skills cannot override Marvex policy",
)


def _python_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


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
    if not SKILLS_RUNTIME.is_dir():
        failures.append("packages/skills_runtime is missing")
    runtime_text = ""
    for path in _python_files(SKILLS_RUNTIME):
        text = path.read_text(encoding="utf-8")
        runtime_text += text
        for token in FORBIDDEN_TEXT:
            if token in text:
                failures.append(f"{_rel(path)} contains forbidden skills runtime token: {token}")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            module = _module_from_import(node)
            if not module:
                continue
            if _matches_prefix(module, FORBIDDEN_IMPORTS):
                failures.append(f"{_rel(path)} imports forbidden skills dependency: {module}")
            if not _matches_prefix(module, ALLOWED_IMPORTS):
                failures.append(f"{_rel(path)} imports non-approved skills dependency: {module}")
    for phrase in REQUIRED_TEXT:
        if phrase not in runtime_text:
            failures.append(f"skills runtime missing required phrase: {phrase}")

    if not SKILL_ADAPTER.is_file() or "packages.skills_runtime" not in SKILL_ADAPTER.read_text(encoding="utf-8"):
        failures.append("packages/adapters/capabilities/skills.py must delegate to packages.skills_runtime")

    for root in NON_OWNER_ROOTS:
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            if "packages.skills_runtime" in text or "SkillManifest" in text:
                failures.append(f"{_rel(path)} must not own SkillsRuntime concepts")

    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_skills_runtime_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_skills_runtime_boundaries.py")

    docs = "\n".join(path.read_text(encoding="utf-8") for path in (VALIDATION_GATES, PROJECT_STATUS) if path.is_file())
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"skills runtime docs/status missing phrase: {phrase}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS skills runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
