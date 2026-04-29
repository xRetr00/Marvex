from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {
    "intent",
    "tools",
    "memory",
    "voice",
    "desktop_context",
    "proactive",
    "vision",
    "ui",
}
ALLOWED_PLACEHOLDERS = {
    "services/intent_worker",
    "services/tool_worker",
    "services/voice_worker",
    "services/desktop_agent",
}
ALLOWED_BOUNDARY_DIRS = {
    "packages/adapters/intent",
    "tests/intent",
}
EXCLUDED_TOP_LEVEL = {"docs", "templates", "scripts"}


def main() -> int:
    failures = []
    for path in ROOT.rglob("*"):
        if not path.is_dir():
            continue
        rel = path.relative_to(ROOT).as_posix()
        top = rel.split("/", 1)[0]
        if top in EXCLUDED_TOP_LEVEL:
            continue
        if rel in ALLOWED_PLACEHOLDERS:
            continue
        if rel in ALLOWED_BOUNDARY_DIRS:
            continue
        if path.name.lower() in FORBIDDEN:
            failures.append(f"forbidden v1 module implementation directory: {rel}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS no forbidden v1 implementation directories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
