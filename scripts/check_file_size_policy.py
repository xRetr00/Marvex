from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_LINES = 500
JUSTIFICATION = "file size justification"
EXCLUDED_PARTS = {"node_modules", "dist", ".venv", ".uv-cache", "gen"}
EXCLUDED_FILENAMES = {"package-lock.json"}
TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
}
STRICT_LIMITS = {
    "packages/capability_runtime/execution.py": 250,
    "packages/assistant_turn_integration/spine.py": 250,
}


def main() -> int:
    failures = []
    for path in ROOT.rglob("*"):
        rel_path = path.relative_to(ROOT)
        rel = rel_path.as_posix()
        rel_parts = rel_path.parts
        if any(part in EXCLUDED_PARTS or part.startswith("uv-cache") for part in rel_parts) or path.name in EXCLUDED_FILENAMES:
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        line_count = len(text.splitlines())
        strict_limit = STRICT_LIMITS.get(rel)
        if strict_limit is not None and line_count > strict_limit:
            failures.append(f"{rel} has {line_count} lines; strict god-file limit is {strict_limit}")
            continue
        if line_count > MAX_LINES and JUSTIFICATION not in text.lower():
            failures.append(f"{rel} has {line_count} lines without file size justification")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS file size policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
