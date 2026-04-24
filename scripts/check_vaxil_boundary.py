from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_VAXIL_REFERENCES = {
    "VAXIL_REFERENCE.md",
    "docs/ARCHITECTURE.md",
    "docs/VALIDATION_GATES.md",
    "scripts/check_vaxil_boundary.py",
}
FORBIDDEN_PATTERNS = [
    "from vaxil",
    "import vaxil",
    "#include \"assistantcontroller",
    "#include <assistantcontroller",
    "copy vaxil code",
    "reuse vaxil code",
    "port vaxil",
]
REFERENCE_PATTERNS = [
    "d:\\vaxil",
    "d:/vaxil",
    "assistantcontroller.cpp",
]


def main() -> int:
    failures = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue

        if rel not in ALLOWED_VAXIL_REFERENCES:
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in text:
                    failures.append(f"forbidden legacy reuse marker in {rel}: {pattern}")

        if rel not in ALLOWED_VAXIL_REFERENCES:
            for pattern in REFERENCE_PATTERNS:
                if pattern in text:
                    failures.append(f"legacy reference outside allowed docs in {rel}: {pattern}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS legacy boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
