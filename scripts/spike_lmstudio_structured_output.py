from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_BASE_URL = "http://localhost:1234/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0
RAW_PREVIEW_LIMIT = 300
ERROR_MESSAGE_LIMIT = 220


class SpikeStructuredResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1.1-draft"]
    response_type: Literal["text", "refusal", "incomplete"]
    text: str = Field(..., min_length=1, max_length=240)
    confidence: float = Field(..., ge=0.0, le=1.0)


@dataclass(frozen=True)
class ObservationCase:
    name: str
    request_mode: str
    input_text: str
    max_output_tokens: int


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    trace_id = f"trace-{uuid4()}"
    client = OpenAI(
        api_key="lm-studio",
        base_url=args.base_url,
        timeout=args.timeout_seconds,
        max_retries=0,
    )

    for case in build_cases():
        lines = run_case(
            client,
            case,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
            trace_id=trace_id,
            show_raw_preview=args.show_raw_preview,
        )
        print("\n".join(lines))
        print()

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spike_lmstudio_structured_output",
        description=(
            "Manual-only LM Studio Responses structured-output observation spike."
        ),
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--show-raw-preview",
        action="store_true",
        help="Print bounded raw fallback previews, never more than 300 chars.",
    )
    return parser


def build_cases() -> list[ObservationCase]:
    return [
        ObservationCase(
            name="valid_structured_success",
            request_mode="responses.parse",
            input_text=(
                "Return a short structured confirmation that the model can "
                "produce the requested schema."
            ),
            max_output_tokens=120,
        ),
        ObservationCase(
            name="invalid_schema_request_pressure",
            request_mode="responses.create.invalid_schema",
            input_text=(
                "This request intentionally uses an invalid JSON schema to "
                "observe provider-side schema error behavior."
            ),
            max_output_tokens=120,
        ),
        ObservationCase(
            name="refusal_like_pressure",
            request_mode="responses.parse",
            input_text=(
                "If policy or model behavior requires refusing a request for "
                "private credential extraction, return a refusal-like answer in "
                "the requested schema. Do not provide credentials."
            ),
            max_output_tokens=120,
        ),
        ObservationCase(
            name="incomplete_length_pressure",
            request_mode="responses.parse",
            input_text=(
                "Return a verbose structured answer, but the caller is "
                "intentionally limiting output tokens to observe incomplete or "
                "length-like response signals."
            ),
            max_output_tokens=8,
        ),
    ]


def run_case(
    client: OpenAI,
    case: ObservationCase,
    *,
    model: str,
    timeout_seconds: float,
    trace_id: str,
    show_raw_preview: bool,
) -> list[str]:
    try:
        if case.request_mode == "responses.create.invalid_schema":
            response = client.responses.create(
                model=model,
                input=case.input_text,
                max_output_tokens=case.max_output_tokens,
                temperature=0,
                text=_invalid_json_schema_text_config(),
                timeout=timeout_seconds,
            )
        else:
            response = client.responses.parse(
                model=model,
                input=case.input_text,
                max_output_tokens=case.max_output_tokens,
                temperature=0,
                text_format=SpikeStructuredResult,
                timeout=timeout_seconds,
            )
    except Exception as exc:
        return error_observation_lines(
            case_name=case.name,
            trace_id=trace_id,
            request_mode=case.request_mode,
            error=exc,
        )

    return observation_lines(
        case_name=case.name,
        trace_id=trace_id,
        request_mode=case.request_mode,
        response=response,
        show_raw_preview=show_raw_preview,
    )


def observation_lines(
    *,
    case_name: str,
    trace_id: str,
    request_mode: str,
    response: object,
    show_raw_preview: bool,
) -> list[str]:
    raw_text = _raw_text(response)
    raw_preview = _preview(raw_text) if show_raw_preview and raw_text else None
    lines = [
        "case: " + case_name,
        "trace_id: " + trace_id,
        "request_mode: " + request_mode,
        "response_status: " + _safe_value(_field(response, "status")),
        "finish_indicator: " + _finish_indicator(response),
        "parsed_structured_object_returned: " + _yes_no(_parsed_present(response)),
        "raw_fallback_text_present: " + _yes_no(bool(raw_text)),
        "refusal_like_signal_present: " + _yes_no(_contains_signal(response, "refusal")),
        "incomplete_length_signal_present: " + _yes_no(_incomplete_signal(response)),
        "error_class: none",
        "error_code: none",
        "error_message: none",
    ]
    if raw_preview is not None:
        lines.append("raw_preview: " + raw_preview)
    return lines


def error_observation_lines(
    *,
    case_name: str,
    trace_id: str,
    request_mode: str,
    error: Exception,
) -> list[str]:
    return [
        "case: " + case_name,
        "trace_id: " + trace_id,
        "request_mode: " + request_mode,
        "response_status: error",
        "finish_indicator: unavailable",
        "parsed_structured_object_returned: no",
        "raw_fallback_text_present: no",
        "refusal_like_signal_present: no",
        "incomplete_length_signal_present: no",
        "error_class: " + type(error).__name__,
        "error_code: " + _safe_value(_error_code(error)),
        "error_message: " + _sanitize_message(str(error)),
    ]


def _invalid_json_schema_text_config() -> dict[str, object]:
    return {
        "format": {
            "type": "json_schema",
            "name": "invalid_marvex_spike_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "required": ["missing_required_property"],
                "properties": {},
            },
        }
    }


def _parsed_present(response: object) -> bool:
    parsed = _field(response, "output_parsed")
    return parsed is not None


def _raw_text(response: object) -> str:
    output_text = _field(response, "output_text")
    if isinstance(output_text, str):
        return output_text
    return ""


def _finish_indicator(response: object) -> str:
    for name in ("status", "finish_reason"):
        value = _field(response, name)
        if value is not None:
            return _safe_value(value)
    incomplete_details = _field(response, "incomplete_details")
    if incomplete_details is not None:
        return "incomplete_details"
    return "unavailable"


def _incomplete_signal(response: object) -> bool:
    status = _field(response, "status")
    if isinstance(status, str) and status.lower() in {"incomplete", "length"}:
        return True
    if _field(response, "incomplete_details") is not None:
        return True
    return _contains_signal(response, "length")


def _contains_signal(value: object, needle: str, *, depth: int = 0) -> bool:
    if depth > 4:
        return False
    if isinstance(value, BaseModel):
        return _contains_signal(value.model_dump(), needle, depth=depth + 1)
    if isinstance(value, dict):
        for key, item in value.items():
            if needle in str(key).lower():
                return True
            if _contains_signal(item, needle, depth=depth + 1):
                return True
        return False
    if isinstance(value, list | tuple):
        return any(_contains_signal(item, needle, depth=depth + 1) for item in value)
    if hasattr(value, "model_dump"):
        return _contains_signal(value.model_dump(), needle, depth=depth + 1)
    if hasattr(value, "__dict__"):
        return _contains_signal(vars(value), needle, depth=depth + 1)
    return False


def _field(value: object, field_name: str) -> object:
    if isinstance(value, dict):
        return value.get(field_name)
    return getattr(value, field_name, None)


def _error_code(error: Exception) -> object:
    for name in ("code", "status_code"):
        value = getattr(error, name, None)
        if value is not None:
            return value
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        return body.get("code") or body.get("type")
    return None


def _sanitize_message(message: str) -> str:
    normalized = " ".join(message.split())
    normalized = normalized.replace("\\", "/")
    if len(normalized) <= ERROR_MESSAGE_LIMIT:
        return normalized
    return normalized[:ERROR_MESSAGE_LIMIT] + "..."


def _preview(text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= RAW_PREVIEW_LIMIT:
        return normalized
    return normalized[:RAW_PREVIEW_LIMIT]


def _safe_value(value: object) -> str:
    if value is None:
        return "none"
    text = str(value)
    if len(text) > ERROR_MESSAGE_LIMIT:
        return text[:ERROR_MESSAGE_LIMIT] + "..."
    return text


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


if __name__ == "__main__":
    raise SystemExit(main())
