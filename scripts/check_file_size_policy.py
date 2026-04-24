from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_LINES = 500
JUSTIFICATION = "file size justification"
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


def main() -> int:
    failures = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        line_count = len(text.splitlines())
        if line_count > MAX_LINES and JUSTIFICATION not in text.lower():
            failures.append(
                f"{path.relative_to(ROOT).as_posix()} has {line_count} lines without file size justification"
            )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS file size policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

