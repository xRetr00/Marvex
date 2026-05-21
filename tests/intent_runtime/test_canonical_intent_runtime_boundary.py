from __future__ import annotations

import ast
from pathlib import Path

from packages.intent_runtime import IntentClassificationRequest, SafeIntentProjection, classify_intent


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RUNTIME_ROOTS = (
    ROOT / "packages" / "cognition_runtime",
    ROOT / "services" / "core",
)
LEGACY_INTENT_IMPORTS = (
    "packages.adapters.intent",
    "packages.ports.intent_router_port",
    "packages.ports.intent_validator_port",
)


def test_runtime_facing_intent_contract_is_safe_projection_not_legacy_intent_decision() -> None:
    result = classify_intent(
        IntentClassificationRequest(
            schema_version="1",
            trace_id="trace-canonical-intent",
            turn_id="turn-canonical-intent",
            user_input_summary="list MCP tools",
        )
    )

    projection = result.safe_projection()

    assert isinstance(projection, SafeIntentProjection)
    assert projection.selected_intent["intent_kind"] == "mcp_needed"
    assert projection.raw_input_persisted is False
    assert "route_family" not in projection.model_dump(mode="json")
    assert "ambiguity_flag" not in projection.model_dump(mode="json")


def test_runtime_and_core_do_not_import_legacy_intent_ports_or_adapters() -> None:
    offenders: list[str] = []
    for root in CANONICAL_RUNTIME_ROOTS:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = _module_from_import(node)
                if module and any(module == legacy or module.startswith(f"{legacy}.") for legacy in LEGACY_INTENT_IMPORTS):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()} imports {module}")

    assert offenders == []


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return None
        return node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None
