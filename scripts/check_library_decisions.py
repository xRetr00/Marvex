from pathlib import Path
import json
import re
import tomllib


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "library name",
    "official source",
    "maintenance status",
    "why use it",
    "why not custom code",
    "fallback if abandoned",
    "pyproject dependency",
    "declared dependency",
]
DECISION_DIR = ROOT / "docs" / "library-decisions"
PYPROJECT = ROOT / "pyproject.toml"
FRONTEND_PACKAGE = ROOT / "apps" / "control_plane_web" / "package.json"
FRONTEND_STACK_DECISION = DECISION_DIR / "control_plane_web_stack.md"
FRONTEND_REQUIRED_NAMES = (
    "react",
    "typescript",
    "vite",
    "tanstack query",
    "tailwind",
    "zod",
    "vitest",
)


def normalize(text: str) -> str:
    return text.lower().replace("_", " ").replace("`", "")


def runtime_dependencies() -> dict[str, str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dependencies = data.get("project", {}).get("dependencies", [])
    results: dict[str, str] = {}
    for dependency in dependencies:
        name_match = re.match(r"\s*([A-Za-z0-9_.-]+)", dependency)
        if name_match:
            results[name_match.group(1).lower().replace("_", "-")] = dependency
    return results


def decision_texts() -> dict[Path, str]:
    if not DECISION_DIR.is_dir():
        return {}
    return {path: path.read_text(encoding="utf-8") for path in sorted(DECISION_DIR.glob("*.md"))}


def validate_runtime_dependency_coverage(failures: list[str]) -> None:
    decisions = decision_texts()
    normalized_decisions = {path: normalize(text) for path, text in decisions.items()}
    for dependency_name, dependency_spec in runtime_dependencies().items():
        matching_paths = [path for path, text in normalized_decisions.items() if f"pyproject dependency: {dependency_name}" in text]
        if not matching_paths:
            failures.append(f"pyproject runtime dependency missing library decision: {dependency_name}")
            continue

        declared = normalize(f"declared dependency: {dependency_spec}")
        if not any(declared in normalized_decisions[path] for path in matching_paths):
            failures.append(f"library decision for {dependency_name} missing declared dependency: {dependency_spec}")


def validate_frontend_dependency_coverage(failures: list[str]) -> None:
    if not FRONTEND_PACKAGE.is_file():
        return
    if not FRONTEND_STACK_DECISION.is_file():
        failures.append("control plane frontend dependencies missing grouped library decision")
        return
    package_data = json.loads(FRONTEND_PACKAGE.read_text(encoding="utf-8"))
    package_deps = set(package_data.get("dependencies", {})) | set(package_data.get("devDependencies", {}))
    if package_deps and not package_data.get("private", False):
        failures.append("control plane frontend package must remain private")
    decision = normalize(FRONTEND_STACK_DECISION.read_text(encoding="utf-8"))
    if "declared dependency: npm package dependencies in apps/control plane web/package.json" not in decision:
        failures.append("control plane frontend stack decision must point at apps/control_plane_web/package.json")
    for name in FRONTEND_REQUIRED_NAMES:
        if name not in decision:
            failures.append(f"control plane frontend stack decision missing library name: {name}")


def main() -> int:
    failures = []
    paths = [ROOT / "docs/LIBRARY_POLICY.md", ROOT / "templates/LIBRARY_DECISION.md"]
    for path in paths:
        if not path.is_file():
            failures.append(f"missing {path.relative_to(ROOT).as_posix()}")
            continue
        text = normalize(path.read_text(encoding="utf-8"))
        for required in REQUIRED:
            if required not in text:
                failures.append(f"{path.relative_to(ROOT).as_posix()} missing library decision field: {required}")

    validate_runtime_dependency_coverage(failures)
    validate_frontend_dependency_coverage(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS library decision policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
