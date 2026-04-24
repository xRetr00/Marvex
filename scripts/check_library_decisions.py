from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "library name",
    "official source",
    "maintenance status",
    "why use it",
    "why not custom code",
    "fallback if abandoned",
]


def normalize(text: str) -> str:
    return text.lower().replace("_", " ")


def main() -> int:
    failures = []
    paths = [
        ROOT / "docs/LIBRARY_POLICY.md",
        ROOT / "templates/LIBRARY_DECISION.md",
    ]
    for path in paths:
        if not path.is_file():
            failures.append(f"missing {path.relative_to(ROOT).as_posix()}")
            continue
        text = normalize(path.read_text(encoding="utf-8"))
        for required in REQUIRED:
            if required not in text:
                failures.append(
                    f"{path.relative_to(ROOT).as_posix()} missing library decision field: {required}"
                )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS library decision policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

