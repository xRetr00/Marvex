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
        if entries != ["README.md"] and not implementation_allowed(contract_name):
            failures.append(
                f"{service.relative_to(ROOT).as_posix()} must contain only README.md until {contract_name} is approved for implementation; found {entries}"
            )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS service placeholders are README-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
