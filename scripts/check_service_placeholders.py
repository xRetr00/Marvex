from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"


def main() -> int:
    failures = []
    if not SERVICES.is_dir():
        print("FAIL missing services directory")
        return 1

    for service in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        entries = sorted(p.name for p in service.iterdir())
        if entries != ["README.md"]:
            failures.append(
                f"{service.relative_to(ROOT).as_posix()} must contain only README.md; found {entries}"
            )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS service placeholders are README-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

