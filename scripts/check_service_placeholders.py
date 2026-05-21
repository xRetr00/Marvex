from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
REGISTRY = ROOT / "docs/CONTRACT_APPROVALS.md"
SERVICE_CONTRACTS = {
    "core": "CoreService",
    "provider_worker": "ProviderWorker",
    "tool_worker": "ToolWorker",
    "intent_worker": "IntentWorker",
    "voice_worker": "VoiceWorker",
    "desktop_agent": "DesktopAgent",
    "shell": "Shell",
}
SERVICE_ENTRYPOINT_TASKS = {"core", "provider_worker"}
ALLOWED_SERVICE_ENTRYPOINT_FILES = {
    "core": {"README.md", "__init__.py", "main.py"},
    "provider_worker": {"README.md", "__init__.py", "models.py", "controller.py", "main.py"},
}
ALLOWED_CORE_SERVICE_IMPORT_PREFIXES = (
    "__future__",
    "argparse",
    "collections.abc",
    "dataclasses",
    "datetime",
    "json",
    "packages.assistant_runtime.input_normalization",
    "packages.contracts",
    "packages.core",
    "packages.core.orchestration.assistant_provider_stage",
    "packages.local_api",
    "packages.runtime_composition",
    "packages.telemetry",
    "subprocess",
    "sys",
    "typing",
    "wsgiref.simple_server",
)
FORBIDDEN_CORE_SERVICE_IMPORT_PREFIXES = (
    "apps",
    "packages.adapters",
    "packages.provider_runtime",
    "packages.process_runtime",
    "services.provider_worker",
    "services.tool_worker",
    "services.intent_worker",
    "services.voice_worker",
    "services.desktop_agent",
    "services.shell",
)
FORBIDDEN_CORE_SERVICE_TOKENS = (
    "packages.adapters",
    "packages.provider_runtime",
    "create_provider",
    "openai",
    "anthropic",
    "gemini",
    "0.0.0.0",
    "memory_runtime",
    "tool_runtime",
    "voice_worker",
    "desktop",
    "proactive",
    "raw prompt",
    "raw_provider",
)


def implementation_allowed(contract_name: str) -> bool:
    if not REGISTRY.is_file():
        return False

    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "---" in line or "contract_name" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6:
            continue
        name, _, status, _, _, allowed = cells
        if name == contract_name:
            return status == "approved" and allowed == "yes"
    return False


def service_entrypoint_allowed(service_name: str, contract_name: str) -> bool:
    return implementation_allowed(contract_name) and service_name in SERVICE_ENTRYPOINT_TASKS


def _module_from_import(node):
    import ast

    if isinstance(node, ast.ImportFrom):
        if node.level:
            return None
        return node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _scan_core_service_entrypoint(service, failures: list[str]) -> None:
    import ast

    allowed_files = ALLOWED_SERVICE_ENTRYPOINT_FILES["core"]
    entries = {path.name for path in service.iterdir() if path.name != "__pycache__"}
    unexpected_entries = sorted(entries - allowed_files)
    if unexpected_entries:
        failures.append(
            f"{service.relative_to(ROOT).as_posix()} contains non-entrypoint files: {unexpected_entries}"
        )

    for path in sorted(service.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.parent != service:
            failures.append(
                f"{path.relative_to(ROOT).as_posix()} is nested runtime/business logic under services/core"
            )
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in FORBIDDEN_CORE_SERVICE_TOKENS:
            if token in lowered:
                failures.append(f"{rel} contains forbidden service entrypoint token: {token}")

        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            if _matches_prefix(module, FORBIDDEN_CORE_SERVICE_IMPORT_PREFIXES):
                failures.append(f"{rel} imports forbidden dependency: {module}")
            if not _matches_prefix(module, ALLOWED_CORE_SERVICE_IMPORT_PREFIXES):
                failures.append(f"{rel} imports non-approved dependency: {module}")


def _scan_provider_worker_entrypoint(service, failures: list[str]) -> None:
    allowed_files = ALLOWED_SERVICE_ENTRYPOINT_FILES["provider_worker"]
    entries = {path.name for path in service.iterdir() if path.name != "__pycache__"}
    unexpected_entries = sorted(entries - allowed_files)
    if unexpected_entries:
        failures.append(
            f"{service.relative_to(ROOT).as_posix()} contains non-entrypoint files: {unexpected_entries}"
        )


def main() -> int:
    failures = []
    if not SERVICES.is_dir():
        print("FAIL missing services directory")
        return 1

    for service in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        contract_name = SERVICE_CONTRACTS.get(service.name)
        if contract_name is None:
            failures.append(
                f"{service.relative_to(ROOT).as_posix()} has no contract mapping"
            )
            continue

        entries = sorted(p.name for p in service.iterdir())
        entrypoint_allowed = service_entrypoint_allowed(service.name, contract_name)
        if entries != ["README.md"] and not entrypoint_allowed:
            failures.append(
                f"{service.relative_to(ROOT).as_posix()} must contain only README.md until {contract_name} is approved and a service-owned entrypoint task updates this gate; found {entries}"
            )
        if service.name == "core" and entrypoint_allowed:
            _scan_core_service_entrypoint(service, failures)
        if service.name == "provider_worker" and entrypoint_allowed:
            _scan_provider_worker_entrypoint(service, failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS service placeholder policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
