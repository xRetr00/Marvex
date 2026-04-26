from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.contracts import ProviderRequest
from packages.provider_runtime import ProviderRuntimeConfig, create_provider


SCHEMA_VERSION = "0.1.1-draft"
PREVIEW_LIMIT = 160
LMSTUDIO_CONTINUITY_FIRST_PROMPT = (
    "Give me one prime number less than 50. Reply with only the number."
)
LMSTUDIO_CONTINUITY_SECOND_PROMPT = "Multiply it by 2. Reply with only the result."


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    model = args.model or "fake-model"

    if args.provider == "fake":
        return _run_single_smoke(
            label="fake smoke",
            provider_name="fake",
            model=model,
            text=args.text,
            instructions=args.instructions,
            previous_response_id=args.previous_response_id,
            provider_options=_provider_options(args),
        )

    if args.provider == "lmstudio_responses":
        return _run_single_smoke(
            label="lmstudio_responses smoke",
            provider_name="lmstudio_responses",
            model=_require_model(args),
            text=args.text,
            instructions=args.instructions,
            previous_response_id=args.previous_response_id,
            provider_options=_provider_options(args),
        )

    if args.provider == "lmstudio_responses_continuity":
        return _run_lmstudio_continuity_smoke(
            model=_require_model(args),
            instructions=args.instructions,
            provider_options=_provider_options(args),
        )

    if args.provider == "litellm":
        return _run_single_smoke(
            label="litellm smoke",
            provider_name="litellm",
            model=_require_model(args),
            text=args.text,
            instructions=args.instructions,
            previous_response_id=args.previous_response_id,
            provider_options=_provider_options(args),
        )

    print(f"FAIL provider smoke: unsupported provider {args.provider}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smoke_providers",
        description="Manual-only Marvex provider smoke harness.",
    )
    parser.add_argument(
        "--provider",
        required=True,
        choices=[
            "fake",
            "lmstudio_responses",
            "lmstudio_responses_continuity",
            "litellm",
        ],
    )
    parser.add_argument("--model")
    parser.add_argument(
        "--text",
        default="Reply with one short sentence confirming the provider works.",
    )
    parser.add_argument("--instructions")
    parser.add_argument("--previous-response-id")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--temperature", type=float)
    return parser


def _run_single_smoke(
    *,
    label: str,
    provider_name: str,
    model: str,
    text: str,
    instructions: str | None,
    previous_response_id: str | None,
    provider_options: dict[str, object],
) -> int:
    request = _make_request(
        model=model,
        text=text,
        instructions=instructions,
        previous_response_id=previous_response_id,
        provider_options=provider_options,
    )
    try:
        response = _send(provider_name, request)
    except Exception as exc:
        print(f"FAIL {label}: unexpected {type(exc).__name__}")
        _print_trace(request.trace_id)
        return 1
    if response.error is not None:
        print(f"FAIL {label}: {response.error.code.value} {_error_type(response.error)}")
        _print_trace(request.trace_id)
        return 1
    if response.output_text == "":
        print(f"FAIL {label}: empty response text")
        _print_trace(request.trace_id)
        return 1

    print(f"PASS {label}")
    _print_response_details(request.trace_id, response.response_id, response.output_text)
    return 0


def _run_lmstudio_continuity_smoke(
    *,
    model: str,
    instructions: str | None,
    provider_options: dict[str, object],
) -> int:
    first_request = _make_request(
        model=model,
        text=LMSTUDIO_CONTINUITY_FIRST_PROMPT,
        instructions=instructions,
        previous_response_id=None,
        provider_options=provider_options,
    )
    try:
        first_response = _send("lmstudio_responses", first_request)
    except Exception as exc:
        print(
            "FAIL lmstudio previous_response_id continuity smoke: "
            f"first request unexpected {type(exc).__name__}"
        )
        _print_trace(first_request.trace_id)
        return 1
    first_error = _validate_continuity_step(
        step="first",
        request=first_request,
        response_id=first_response.response_id,
        output_text=first_response.output_text,
        error=first_response.error,
    )
    if first_error is not None:
        print(f"FAIL lmstudio previous_response_id continuity smoke: {first_error}")
        _print_trace(first_request.trace_id)
        return 1

    second_request = _make_request(
        model=model,
        text=LMSTUDIO_CONTINUITY_SECOND_PROMPT,
        instructions=instructions,
        previous_response_id=first_response.response_id,
        provider_options=provider_options,
    )
    try:
        second_response = _send("lmstudio_responses", second_request)
    except Exception as exc:
        print(
            "FAIL lmstudio previous_response_id continuity smoke: "
            f"second request unexpected {type(exc).__name__}"
        )
        _print_trace(second_request.trace_id)
        return 1
    second_error = _validate_continuity_step(
        step="second",
        request=second_request,
        response_id=second_response.response_id,
        output_text=second_response.output_text,
        error=second_response.error,
    )
    if second_error is not None:
        print(f"FAIL lmstudio previous_response_id continuity smoke: {second_error}")
        _print_trace(second_request.trace_id)
        return 1

    print("PASS lmstudio previous_response_id continuity smoke")
    _print_response_details(
        first_request.trace_id,
        first_response.response_id,
        first_response.output_text,
        prefix="first",
    )
    _print_response_details(
        second_request.trace_id,
        second_response.response_id,
        second_response.output_text,
        prefix="second",
    )
    return 0


def _make_request(
    *,
    model: str,
    text: str,
    instructions: str | None,
    previous_response_id: str | None,
    provider_options: dict[str, object],
) -> ProviderRequest:
    trace_id = f"trace-{uuid4()}"
    return ProviderRequest(
        schema_version=SCHEMA_VERSION,
        trace_id=trace_id,
        turn_id=f"turn-{uuid4()}",
        model=model,
        input_text=text,
        instructions=instructions,
        previous_response_id=previous_response_id,
        provider_options=provider_options,
    )


def _send(provider_name: str, request: ProviderRequest):
    provider = create_provider(ProviderRuntimeConfig(provider_name=provider_name))
    return provider.send(request)


def _error_type(error: object) -> str:
    details = getattr(error, "details", {})
    if isinstance(details, dict):
        exception_type = details.get("exception_type")
        if isinstance(exception_type, str) and exception_type != "":
            return f"({exception_type})"
    return ""


def _validate_continuity_step(
    *,
    step: str,
    request: ProviderRequest,
    response_id: str | None,
    output_text: str,
    error: object | None,
) -> str | None:
    if error is not None:
        return f"{step} request returned provider error"
    if output_text == "":
        return f"{step} response text was empty"
    if response_id is None:
        return f"{step} provider response_id was empty"
    if request.trace_id == "":
        return f"{step} trace_id was empty"
    return None


def _provider_options(args: argparse.Namespace) -> dict[str, object]:
    options: dict[str, object] = {}
    if args.timeout is not None:
        options["timeout"] = args.timeout
    if args.temperature is not None:
        options["temperature"] = args.temperature
    return options


def _require_model(args: argparse.Namespace) -> str:
    if args.model is None or args.model == "":
        print(f"FAIL {args.provider} smoke: --model is required")
        raise SystemExit(2)
    return args.model


def _print_response_details(
    trace_id: str,
    response_id: str | None,
    output_text: str,
    *,
    prefix: str | None = None,
) -> None:
    label = f"{prefix}_" if prefix is not None else ""
    print(f"{label}response_id: {response_id or ''}")
    print(f"{label}trace_id: {trace_id}")
    print(f"{label}response_preview: {_preview(output_text)}")


def _print_trace(trace_id: str) -> None:
    print(f"trace_id: {trace_id}")


def _preview(text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= PREVIEW_LIMIT:
        return normalized
    return f"{normalized[:PREVIEW_LIMIT]}..."


if __name__ == "__main__":
    raise SystemExit(main())
