from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {
    ".py",
    ".pyw",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".rs",
    ".go",
    ".java",
    ".cs",
}


def docs_accepted() -> bool:
    status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8").lower()
    return "accepted_docs: true" in status


def main() -> int:
    if docs_accepted():
        print("PASS docs accepted")
        return 0

    failures = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() in SOURCE_SUFFIXES and not rel.startswith("scripts/"):
            failures.append(f"implementation blocked until docs are accepted: {rel}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS docs not accepted; workspace remains planning-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

