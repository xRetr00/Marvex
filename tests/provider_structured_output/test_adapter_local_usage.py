from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from packages.provider_structured_output import map_adapter_raw_output_to_structured_result


ROOT = Path(__file__).resolve().parents[2]
HELPER_MODULE = ROOT / "packages" / "provider_structured_output" / "adapter_local.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "packages.core",
    "packages.provider_runtime",
    "packages.assistant_runtime",
    "packages.adapters",
    "packages.ports",
    "apps.cli",
    "services",
)


class DemoPayload(BaseModel):
    text: str = Field(..., min_length=1)
    count: int


def _map(raw_output_text: str, *, include_raw_preview: bool = False):
    return map_adapter_raw_output_to_structured_result(
        schema_version="0.1.1-draft",
        trace_id="trace-adapter-001",
        turn_id="turn-adapter-001",
        target_contract="DemoPayload",
        raw_output_text=raw_output_text,
        target_model=DemoPayload,
        include_raw_preview=include_raw_preview,
    )


def test_adapter_local_helper_returns_valid_result_for_whole_output_json():
    result = _map('{"text": "Done.", "count": 2}')

    assert result.state == "valid_structured_result"
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-adapter-001"
    assert result.turn_id == "turn-adapter-001"
    assert result.target_contract == "DemoPayload"
    assert result.parsed_payload == {"text": "Done.", "count": 2}
    assert result.raw_preview is None


@pytest.mark.parametrize(
    "raw_output_text",
    [
        '{"text": "unterminated"',
        'Here is JSON: {"text": "Done.", "count": 2}',
    ],
)
def test_adapter_local_helper_rejects_invalid_or_prose_wrapped_json(
    raw_output_text: str,
):
    result = _map(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.sanitized_error_code == "INVALID_JSON"
    assert result.parsed_payload is None
    assert result.raw_preview is None


def test_adapter_local_helper_can_opt_into_bounded_raw_preview():
    result = _map("x" * 350, include_raw_preview=True)

    assert result.state == "invalid_structured_output"
    assert result.raw_preview == "x" * 300


def test_adapter_local_helper_sanitizes_raw_and_validation_errors():
    raw_output_text = '{"text": "", "count": "secret-invalid-value"}'

    result = _map(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.sanitized_message == "Structured output failed target validation."
    assert raw_output_text not in result.sanitized_message
    assert "secret-invalid-value" not in result.sanitized_message
    assert "count" not in result.sanitized_message
    assert result.raw_preview is None


def test_adapter_local_helper_imports_do_not_cross_runtime_boundaries():
    tree = ast.parse(HELPER_MODULE.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    assert not [
        module
        for module in imports
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        )
    ]
