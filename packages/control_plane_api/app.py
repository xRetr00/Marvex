from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs

from packages.contracts import ErrorCode, ErrorEnvelope
from packages.local_api.auth_policy import validate_local_bearer_token
from packages.marketplace_runtime import McpAllowlistProposal, MarketplaceEnablementState
from packages.memory_runtime import MemoryRef
from packages.telemetry.search import TraceSearchQuery, search_traces

from .approvals import InMemoryApprovalStore
from .models import ApprovalDecisionInput, ApprovalDecisionResponse, ControlPlaneSnapshot


StartResponse = Any
WsgiApp = Any
SCHEMA_VERSION = "1"
CONTROL_PREFIX = "/control"


def create_control_plane_api_app(
    *,
    approval_store: InMemoryApprovalStore,
    snapshot: ControlPlaneSnapshot,
    local_auth_token: str,
    approval_history: tuple[ApprovalDecisionResponse, ...] = (),
    mcp_marketplace: Any | None = None,
    skills_marketplace: Any | None = None,
    memory_store: Any | None = None,
    trace_reader: Any | None = None,
    trace_ids: tuple[str, ...] = (),
    policy_views: tuple[dict[str, Any], ...] = (),
    diagnostics: dict[str, Any] | None = None,
) -> WsgiApp:
    def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        raw_path = str(environ.get("PATH_INFO", "/"))
        path, _separator, inline_query = raw_path.partition("?")
        query_string = str(environ.get("QUERY_STRING") or inline_query)
        auth_error = validate_local_bearer_token(
            authorization_header=_authorization_header(environ),
            expected_token=local_auth_token,
            trace_id="trace-control-plane-auth-required",
        )
        if auth_error is not None:
            return _json_response(start_response, "401 Unauthorized", auth_error.model_dump(mode="json"))

        if method == "GET" and path == f"{CONTROL_PREFIX}/approvals":
            return _json_response(start_response, "200 OK", approval_store.list_pending().model_dump(mode="json"))
        if method == "GET" and path == f"{CONTROL_PREFIX}/approvals/history":
            history = approval_store.list_history()
            decisions = tuple(history.decisions) + tuple(approval_history)
            payload = {
                "schema_version": SCHEMA_VERSION,
                "decisions": [decision.model_dump(mode="json") for decision in decisions],
                "decision_count": len(decisions),
                "raw_payload_persisted": False,
            }
            return _json_response(start_response, "200 OK", payload)
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/approvals/"):
            approval_id, action = _approval_path(path)
            if action is not None:
                return _json_response(start_response, "404 Not Found", _error("not_found", path))
            approval = approval_store.read_pending(approval_id)
            if approval is None:
                return _json_response(start_response, "404 Not Found", _error("approval_not_found", path))
            return _json_response(start_response, "200 OK", approval.model_dump(mode="json"))
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/approvals/"):
            approval_id, action = _approval_path(path)
            if action not in {"approve", "deny"}:
                return _json_response(start_response, "404 Not Found", _error("not_found", path))
            decision_input = _parse_decision_input(environ)
            if isinstance(decision_input, ErrorEnvelope):
                return _json_response(start_response, "400 Bad Request", decision_input.model_dump(mode="json"))
            decision = (
                approval_store.approve(approval_id, reason=decision_input.reason)
                if action == "approve"
                else approval_store.deny(approval_id, reason=decision_input.reason)
            )
            if decision is None:
                return _json_response(start_response, "404 Not Found", _error("approval_not_found", path))
            return _json_response(start_response, "200 OK", decision.model_dump(mode="json"))
        if method == "GET" and path == f"{CONTROL_PREFIX}/marketplace/mcp":
            entries = tuple(mcp_marketplace.safe_projection()) if mcp_marketplace is not None else ()
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "entries": entries, "read_only_browse": True, "raw_payload_persisted": False})
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/marketplace/mcp/") and path.endswith("/disable"):
            server_id = path.removeprefix(f"{CONTROL_PREFIX}/marketplace/mcp/").removesuffix("/disable").strip("/")
            state = MarketplaceEnablementState.disabled(subject_id=server_id, subject_kind="mcp_server", reason_code="disabled_by_control_plane")
            return _json_response(start_response, "200 OK", state.safe_projection())
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/marketplace/mcp/") and path.endswith("/allowlist-proposals"):
            server_id = path.removeprefix(f"{CONTROL_PREFIX}/marketplace/mcp/").removesuffix("/allowlist-proposals").strip("/")
            entry = _find_entry(mcp_marketplace, server_id)
            if entry is None:
                return _json_response(start_response, "404 Not Found", _error("mcp_marketplace_entry_not_found", path))
            proposal = McpAllowlistProposal.from_entry(entry, proposal_id=f"allowlist:{server_id}", requested_by="control_plane")
            return _json_response(start_response, "200 OK", proposal.safe_projection())
        if method == "GET" and path == f"{CONTROL_PREFIX}/marketplace/skills":
            entries = tuple(skills_marketplace.safe_projection()) if skills_marketplace is not None else ()
            previews = tuple(_skill_previews(skills_marketplace)) if skills_marketplace is not None else ()
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "entries": entries, "previews": previews, "raw_payload_persisted": False})
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/marketplace/skills/") and path.endswith("/disable"):
            skill_id = path.removeprefix(f"{CONTROL_PREFIX}/marketplace/skills/").removesuffix("/disable").strip("/")
            state = MarketplaceEnablementState.disabled(subject_id=skill_id, subject_kind="skill", reason_code="disabled_by_control_plane")
            return _json_response(start_response, "200 OK", state.safe_projection())
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/marketplace/skills/") and path.endswith("/enable"):
            skill_id = path.removeprefix(f"{CONTROL_PREFIX}/marketplace/skills/").removesuffix("/enable").strip("/")
            state = MarketplaceEnablementState.with_enabled(subject_id=skill_id, subject_kind="skill", reason_code="validated_local_manifest")
            return _json_response(start_response, "200 OK", state.safe_projection())
        if method == "GET" and path == f"{CONTROL_PREFIX}/memory":
            records = tuple(memory_store.safe_inspect()) if memory_store is not None and hasattr(memory_store, "safe_inspect") else ()
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "records": records, "record_count": len(records), "raw_transcript_persisted": False})
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/memory/") and path.endswith("/forget"):
            memory_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/").removesuffix("/forget").strip("/")
            if memory_store is None:
                return _json_response(start_response, "404 Not Found", _error("memory_store_not_configured", path))
            result = memory_store.forget(MemoryRef(ref_type="memory", ref_id=memory_id))
            return _json_response(start_response, "200 OK", result.safe_projection())
        if method == "GET" and path == f"{CONTROL_PREFIX}/traces/search":
            query = _trace_search_query(query_string)
            result = search_traces(trace_reader, query, trace_ids=trace_ids) if trace_reader is not None else None
            payload = result.safe_projection() if result is not None else {"schema_version": SCHEMA_VERSION, "traces": [], "match_count": 0, "truncated": False, "raw_payload_persisted": False}
            return _json_response(start_response, "200 OK", payload)
        if method == "GET" and path == f"{CONTROL_PREFIX}/policies":
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "policies": tuple(_safe_mapping(policy) for policy in policy_views), "raw_payload_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/diagnostics":
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, **_safe_mapping(diagnostics or {}), "raw_payload_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/snapshot":
            payload = snapshot.model_dump(mode="json")
            payload["approvals"] = approval_store.list_pending().model_dump(mode="json")
            return _json_response(start_response, "200 OK", payload)
        if method == "GET" and path == f"{CONTROL_PREFIX}/health":
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "status": "ok"})
        if method == "GET" and path == f"{CONTROL_PREFIX}/version":
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "service": "marvex-control-plane-api"})
        return _json_response(start_response, "404 Not Found", _error("not_found", path))

    return app


def _approval_path(path: str) -> tuple[str, str | None]:
    tail = path.removeprefix(f"{CONTROL_PREFIX}/approvals/").strip("/")
    parts = tail.split("/") if tail else []
    if len(parts) == 1:
        return parts[0], None
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", "invalid"


def _parse_decision_input(environ: dict[str, Any]) -> ApprovalDecisionInput | ErrorEnvelope:
    try:
        payload = json.loads(_read_request_body(environ))
        return ApprovalDecisionInput.model_validate(payload)
    except Exception:
        return ErrorEnvelope(
            schema_version="0.1.1-draft",
            trace_id="trace-control-plane-validation-error",
            error_id="control-plane-validation-error",
            code=ErrorCode.VALIDATION_ERROR,
            message="Control Plane request validation failed.",
            recoverable=False,
            source="control_plane_api",
            details={"reason": "invalid_decision_request"},
        )


def _read_request_body(environ: dict[str, Any]) -> str:
    length_text = str(environ.get("CONTENT_LENGTH") or "0")
    content_length = int(length_text) if length_text.strip() else 0
    stream = environ["wsgi.input"]
    raw_body = stream.read(content_length)
    return raw_body.decode("utf-8") if isinstance(raw_body, bytes) else str(raw_body)


def _authorization_header(environ: dict[str, Any]) -> str | None:
    value = environ.get("HTTP_AUTHORIZATION")
    return value if isinstance(value, str) else None


def _trace_search_query(query_string: str) -> TraceSearchQuery:
    params = parse_qs(query_string, keep_blank_values=False)
    return TraceSearchQuery(
        schema_version=SCHEMA_VERSION,
        session_ref_id=_first(params, "session_ref_id"),
        conversation_ref_id=_first(params, "conversation_ref_id"),
        tool_status=_first(params, "tool_status"),
        approval_status=_first(params, "approval_status"),
        status=_first(params, "status"),
        max_results=int(_first(params, "max_results") or 25),
    )


def _first(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key)
    return values[0] if values else None


def _find_entry(catalog: Any | None, server_id: str) -> Any | None:
    for entry in getattr(catalog, "entries", ()) if catalog is not None else ():
        if getattr(entry, "server_id", None) == server_id:
            return entry
    return None


def _skill_previews(catalog: Any) -> tuple[dict[str, object], ...]:
    previews: list[dict[str, object]] = []
    for entry in getattr(catalog, "entries", ()):
        previews.append({"skill_id": entry.skill_id, "preview": entry.prompt_contribution_preview(max_chars=300), "raw_instruction_persisted": False})
    return tuple(previews)


def _safe_mapping(value: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        normalized = key_text.lower().replace("-", "_")
        if normalized.startswith("raw_") or any(part in normalized for part in ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey")):
            continue
        if isinstance(item, str):
            lowered = item.lower()
            safe[key_text] = "[redacted]" if any(part in lowered for part in ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey")) else item
        elif isinstance(item, int | float | bool) or item is None:
            safe[key_text] = item
    return safe


def _error(reason: str, path: str) -> dict[str, Any]:
    return ErrorEnvelope(
        schema_version="0.1.1-draft",
        trace_id="trace-control-plane-error",
        error_id="control-plane-error",
        code=ErrorCode.NOT_FOUND,
        message="Control Plane endpoint not found." if reason == "not_found" else "Control Plane resource not found.",
        recoverable=False,
        source="control_plane_api",
        details={"reason": reason, "path": path},
    ).model_dump(mode="json")


def _json_response(start_response: StartResponse, status: str, payload: dict[str, Any]) -> list[bytes]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body)))], None)
    return [body]
