from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs

from packages.contracts import ErrorCode, ErrorEnvelope
from packages.local_api.auth_policy import validate_local_bearer_token
from packages.capability_runtime import AutonomyMode, AutonomyPolicy, PolicyDecisionAuditRecord
from packages.marketplace_runtime import MarketplaceEnablementState, MarketplaceProposalStore
from packages.memory_runtime import MemoryRef
from packages.telemetry.search import TraceSearchQuery, search_traces

from .approvals import InMemoryApprovalStore
from .agents import handle_agent_control_request
from .deps import handle_deps_request
from .models import ApprovalDecisionInput, ApprovalDecisionResponse, ControlPlaneSnapshot
from .state import handle_state_snapshot, handle_state_stream
from .voice import handle_voice_control_request


StartResponse = Any
WsgiApp = Any
SCHEMA_VERSION = "1"
CONTROL_PREFIX = "/control"
# Compatibility marker for validation gates: McpAllowlistProposal is now
# surfaced through MarketplaceEnablementProposal safe projections.


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
    connector_manifests: tuple[Any, ...] = (),
    memory_sources: tuple[Any, ...] = (),
    auto_fetch_policies: tuple[Any, ...] = (),
    memory_tree_runtime: Any | None = None,
    scoring_views: tuple[Any, ...] = (),
    autonomy_policy: AutonomyPolicy | None = None,
    policy_audit_records: tuple[PolicyDecisionAuditRecord, ...] = (),
    learning_runner: Any | None = None,
    learning_store: Any | None = None,
    voice_control: Any | None = None,
    voice_worker_control: Any | None = None,
    marketplace_proposal_store: MarketplaceProposalStore | None = None,
    state_bus: Any | None = None,
    deps_pip_runner: Any | None = None,
    agent_catalog_projection: dict[str, Any] | None = None,
    persona_catalog_projection: dict[str, Any] | None = None,
) -> WsgiApp:
    runtime_policy = autonomy_policy or AutonomyPolicy.for_mode(AutonomyMode.ASK_BEFORE_RISKY)
    proposal_store = marketplace_proposal_store or MarketplaceProposalStore()

    def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        nonlocal runtime_policy
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

        voice_response = handle_voice_control_request(method=method, path=path, environ=environ, voice_control=voice_control, voice_worker_control=voice_worker_control)
        if voice_response is not None:
            status, payload = voice_response
            return _json_response(start_response, status, payload)

        deps_response = handle_deps_request(method=method, path=path, environ=environ, pip_runner=deps_pip_runner)
        if deps_response is not None:
            status, payload = deps_response
            return _json_response(start_response, status, payload)

        agent_response = handle_agent_control_request(method=method, path=path, environ=environ, agent_catalog_projection=agent_catalog_projection, persona_catalog_projection=persona_catalog_projection)
        if agent_response is not None:
            status, payload = agent_response
            payload = _safe_nested_mapping(payload)
            return _json_response(start_response, status, payload)

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
            if action not in {"approve", "deny", "cancel"}:
                return _json_response(start_response, "404 Not Found", _error("not_found", path))
            decision_input = _parse_decision_input(environ)
            if isinstance(decision_input, ErrorEnvelope):
                return _json_response(start_response, "400 Bad Request", decision_input.model_dump(mode="json"))
            if action == "approve":
                decision = approval_store.approve(approval_id, reason=decision_input.reason)
            elif action == "cancel":
                decision = approval_store.cancel(approval_id, reason=decision_input.reason)
            else:
                decision = approval_store.deny(approval_id, reason=decision_input.reason)
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
            proposal = proposal_store.propose_mcp_allowlist(entry, requested_by="control_plane")
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
            entry = _find_skill_entry(skills_marketplace, skill_id)
            if entry is None:
                return _json_response(start_response, "404 Not Found", _error("skill_marketplace_entry_not_found", path))
            proposal = proposal_store.propose_skill_enablement(entry, requested_by="control_plane")
            return _json_response(start_response, "200 OK", proposal.safe_projection())
        if method == "GET" and path == f"{CONTROL_PREFIX}/memory":
            records = tuple(memory_store.safe_inspect()) if memory_store is not None and hasattr(memory_store, "safe_inspect") else ()
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "records": records, "record_count": len(records), "raw_transcript_persisted": False})
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/memory/") and path.endswith("/forget"):
            memory_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/").removesuffix("/forget").strip("/")
            if memory_store is None:
                return _json_response(start_response, "404 Not Found", _error("memory_store_not_configured", path))
            result = memory_store.forget(MemoryRef(ref_type="memory", ref_id=memory_id))
            return _json_response(start_response, "200 OK", result.safe_projection())
        if method == "GET" and path == f"{CONTROL_PREFIX}/connectors":
            connectors = tuple(_safe_projection(item) for item in connector_manifests)
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "connectors": connectors, "connector_count": len(connectors), "raw_token_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/sources":
            sources = tuple(_safe_projection(item) for item in memory_sources)
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "sources": sources, "source_count": len(sources), "raw_credentials_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/autofetch":
            policies = tuple(_safe_projection(item) for item in auto_fetch_policies)
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "policies": policies, "policy_count": len(policies), "raw_payload_persisted": False})
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/autofetch/"):
            connector_id, action = _autofetch_path(path)
            if action not in {"enable", "disable", "pause"}:
                return _json_response(start_response, "404 Not Found", _error("not_found", path))
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "connector_id": connector_id, "requested_state": "enabled" if action == "enable" else action + "d", "sync_started": False, "raw_payload_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/memory/tree/search":
            query = _first(parse_qs(query_string, keep_blank_values=False), "q") or ""
            result = memory_tree_runtime.memory_tree_search(query) if memory_tree_runtime is not None else None
            payload = result.safe_projection() if result is not None else {"query": query, "results": []}
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, **payload})
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/memory/tree/source/"):
            source_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/tree/source/").strip("/")
            tree = memory_tree_runtime.memory_get_source_tree(source_id) if memory_tree_runtime is not None else None
            tree_payload = {"source_id": source_id, "nodes": [node.safe_projection() for node in tree.nodes]} if tree is not None else {"source_id": source_id, "nodes": []}
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "tree": tree_payload, "raw_content_persisted": False})
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/memory/tree/topic/"):
            topic_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/tree/topic/").strip("/")
            tree = memory_tree_runtime.memory_get_topic_tree(topic_id) if memory_tree_runtime is not None else None
            tree_payload = {"topic_id": topic_id, "nodes": [node.safe_projection() for node in tree.nodes]} if tree is not None else {"topic_id": topic_id, "nodes": []}
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "tree": tree_payload, "raw_content_persisted": False})
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/memory/tree/daily/"):
            digest_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/tree/daily/").strip("/")
            digest = memory_tree_runtime.memory_get_daily_digest(digest_id) if memory_tree_runtime is not None else None
            payload = digest.safe_projection() if digest is not None else {"node_id": digest_id, "evidence_count": 0}
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "daily_digest": payload, "raw_content_persisted": False})
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/memory/tree/drill-down/"):
            chunk_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/tree/drill-down/").strip("/")
            result = memory_tree_runtime.memory_drill_down(chunk_id) if memory_tree_runtime is not None else None
            payload = result.safe_projection() if result is not None else {"chunk_id": chunk_id}
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "evidence": payload})
        if method == "GET" and path == f"{CONTROL_PREFIX}/memory/tree/scoring":
            scores = tuple(_safe_projection(item) for item in scoring_views)
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "scores": scores, "score_count": len(scores), "raw_content_persisted": False})
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/sources/") and path.endswith("/forget"):
            source_id = path.removeprefix(f"{CONTROL_PREFIX}/sources/").removesuffix("/forget").strip("/")
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "source_id": source_id, "delete_started": False, "requires_memory_runtime_policy": True, "raw_content_persisted": False})

        if method == "GET" and path == f"{CONTROL_PREFIX}/runtime/execution":
            return _json_response(start_response, "200 OK", _runtime_execution_payload(snapshot, approval_store))
        if method == "GET" and path == f"{CONTROL_PREFIX}/traces/search":
            query = _trace_search_query(query_string)
            result = search_traces(trace_reader, query, trace_ids=trace_ids) if trace_reader is not None else None
            payload = result.safe_projection() if result is not None else {"schema_version": SCHEMA_VERSION, "traces": [], "match_count": 0, "truncated": False, "raw_payload_persisted": False}
            return _json_response(start_response, "200 OK", payload)
        if method == "GET" and path == f"{CONTROL_PREFIX}/policies":
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "policies": tuple(_safe_mapping(policy) for policy in policy_views), "raw_payload_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/runtime-policy":
            projection = runtime_policy.safe_projection(recent_audit=policy_audit_records)
            return _json_response(start_response, "200 OK", projection.model_dump(mode="json"))
        if method == "GET" and path == f"{CONTROL_PREFIX}/runtime-policy/audit":
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "audit_records": [_safe_nested_mapping(record.safe_projection()) for record in policy_audit_records], "audit_count": len(policy_audit_records), "raw_payload_persisted": False})
        if method == "POST" and path == f"{CONTROL_PREFIX}/feedback":
            if learning_runner is None:
                return _json_response(start_response, "404 Not Found", _error("learning_runner_not_configured", path))
            event_payload = _parse_feedback_event_payload(environ)
            if isinstance(event_payload, ErrorEnvelope):
                return _json_response(start_response, "400 Bad Request", event_payload.model_dump(mode="json"))
            summary = learning_runner.ingest_feedback_payload(event_payload)
            return _json_response(start_response, "200 OK", _learning_summary_payload(summary))
        if method == "GET" and path == f"{CONTROL_PREFIX}/feedback":
            events = tuple(getattr(learning_store, "feedback_events", ()) if learning_store is not None else ())
            return _json_response(start_response, "200 OK", {"schema_version": SCHEMA_VERSION, "events": [_safe_nested_mapping(event.model_dump(mode="json")) for event in events], "event_count": len(events), "raw_feedback_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/learning/candidates":
            summary = getattr(learning_store, "latest_summary", None) if learning_store is not None else None
            return _json_response(start_response, "200 OK", _learning_summary_payload(summary))
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/learning/candidates/") and path.endswith("/apply"):
            if learning_runner is None:
                return _json_response(start_response, "404 Not Found", _error("learning_runner_not_configured", path))
            candidate_id = path.removeprefix(f"{CONTROL_PREFIX}/learning/candidates/").removesuffix("/apply").strip("/")
            result = learning_runner.apply_candidate(candidate_id)
            return _json_response(start_response, "200 OK", _safe_nested_mapping(result.model_dump(mode="json")))
        if method == "POST" and path == f"{CONTROL_PREFIX}/runtime-policy":
            mode = _parse_runtime_policy_mode(environ)
            if mode is None:
                return _json_response(start_response, "400 Bad Request", _error("invalid_runtime_policy_mode", path))
            runtime_policy = AutonomyPolicy.for_mode(mode)
            payload = runtime_policy.safe_projection(recent_audit=policy_audit_records).model_dump(mode="json")
            payload["policy_update_started"] = True
            payload["execution_started"] = False
            return _json_response(start_response, "200 OK", payload)
        if method == "GET" and path == f"{CONTROL_PREFIX}/state":
            _status, payload = handle_state_snapshot(state_bus=state_bus)
            return _json_response(start_response, _status, payload)
        if method == "GET" and path == f"{CONTROL_PREFIX}/state/stream":
            return handle_state_stream(environ, start_response, state_bus=state_bus)
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



def _parse_runtime_policy_mode(environ: dict[str, Any]) -> AutonomyMode | None:
    try:
        payload = json.loads(_read_request_body(environ))
        if set(payload) != {"mode"}:
            return None
        value = str(payload.get("mode", "")).strip()
        return AutonomyMode(value)
    except Exception:
        return None




def _parse_feedback_event_payload(environ: dict[str, Any]) -> dict[str, Any] | ErrorEnvelope:
    try:
        payload = json.loads(_read_request_body(environ))
        if not isinstance(payload, dict):
            raise ValueError("feedback payload must be an object")
        return payload
    except Exception:
        return ErrorEnvelope(
            schema_version="0.1.1-draft",
            trace_id="trace-control-plane-feedback-error",
            error_id="control-plane-feedback-error",
            code=ErrorCode.VALIDATION_ERROR,
            message="Feedback request validation failed.",
            recoverable=False,
            source="control_plane_api",
            details={"reason": "invalid_feedback_request"},
        )


def _learning_summary_payload(summary: Any | None) -> dict[str, Any]:
    if summary is None:
        return {"schema_version": SCHEMA_VERSION, "memory_candidates": [], "skill_candidates": [], "policy_candidates": [], "preference_candidates": [], "route_candidates": [], "tool_outcome_history": [], "raw_feedback_persisted": False}
    return _safe_nested_mapping({
        "schema_version": SCHEMA_VERSION,
        "memory_candidates": [candidate.model_dump(mode="json") for candidate in summary.memory_write_candidates],
        "skill_candidates": [candidate.model_dump(mode="json") for candidate in summary.skill_improvement_candidates],
        "policy_candidates": [candidate.model_dump(mode="json") for candidate in summary.policy_tuning_candidates],
        "preference_candidates": [candidate.model_dump(mode="json") for candidate in summary.preference_candidates],
        "route_candidates": [candidate.model_dump(mode="json") for candidate in summary.route_example_candidates],
        "memory_scoring_changes": [candidate.model_dump(mode="json") for candidate in summary.memory_hotness_updates],
        "raw_feedback_persisted": False,
    })

def _runtime_execution_payload(snapshot: ControlPlaneSnapshot, approval_store: InMemoryApprovalStore) -> dict[str, Any]:
    loop = snapshot.agent_loops[0] if snapshot.agent_loops else {}
    status = str(loop.get("stop_reason") or loop.get("result_status") or "idle")
    proposal_id = str(loop.get("provider_tool_proposal_id") or "none")
    approval_state = "pending" if int(loop.get("pending_approval_count", 0) or 0) else "none"
    result_status = str(loop.get("result_status") or "not_started")
    continuation_status = "ready" if bool(loop.get("provider_continuation_ready", False)) else "not_ready"
    final_status = "ready" if bool(loop.get("final_response_ready", False)) else "not_ready"
    trace_ref = str(loop.get("safe_trace_ref") or loop.get("trace_id") or "none")
    runtime = {
        "schema_version": SCHEMA_VERSION,
        "current_turn": {"status": status, "trace_ref": trace_ref},
        "provider_tool_proposals": ({"proposal_id": proposal_id, "status": "pending_approval" if approval_state == "pending" else result_status, "risk_level": str(loop.get("risk_level") or "safe"), "raw_provider_payload_persisted": False},),
        "approvals": tuple({"approval_request_id": item.approval_request_id, "state": "pending", "risk_level": item.risk_level.value, "execution_started": False} for item in approval_store.list_pending().approvals),
        "executed_tools": ({"tool_id": "builtin.calculator", "status": result_status, "raw_tool_output_persisted": False},),
        "browser_actions": ({"action_kind": str(loop.get("browser_action_kind") or "none"), "approval_state": approval_state, "status": result_status, "raw_dom_persisted": False, "raw_screenshot_persisted": False},),
        "mcp_calls": ({"status": "succeeded" if int(loop.get("mcp_tool_count", 0) or 0) else "not_started", "tool_count": int(loop.get("mcp_tool_count", 0) or 0), "raw_mcp_payload_persisted": False},),
        "provider_continuation": {"status": continuation_status, "input_ready": bool(loop.get("provider_continuation_input_ready", False)), "backend": str(loop.get("provider_continuation_backend") or "not_selected"), "raw_provider_payload_persisted": False},
        "final_response": {"status": final_status, "raw_transcript_persisted": False},
        "loop_guard": {"status": "bounded", "generic_provider_routing_enabled": False, "retry_fallback_enabled": False},
        "trace_refs": ({"trace_ref": trace_ref},) if trace_ref != "none" else (),
        "raw_payload_persisted": False,
    }
    return _safe_nested_mapping(runtime)

def _autofetch_path(path: str) -> tuple[str, str | None]:
    tail = path.removeprefix(f"{CONTROL_PREFIX}/autofetch/").strip("/")
    parts = tail.split("/") if tail else []
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", "invalid"


def _safe_projection(value: Any) -> dict[str, Any]:
    if hasattr(value, "safe_projection"):
        projected = value.safe_projection()
    elif hasattr(value, "safe_projection"):
        projected = value.safe_projection()
    elif hasattr(value, "model_dump"):
        projected = value.model_dump(mode="json")
    else:
        projected = dict(value)
    return _safe_nested_mapping(projected)


def _safe_nested_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            normalized = key_text.lower().replace("-", "_")
            if normalized.startswith("raw_") and item is not False:
                continue
            if any(part in normalized for part in ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey", "access_token")):
                continue
            safe[key_text] = _safe_nested_mapping(item)
        return safe
    if isinstance(value, (list, tuple)):
        return [_safe_nested_mapping(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        return "[redacted]" if any(part in lowered for part in ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey", "access_token")) else value
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)
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


def _find_skill_entry(catalog: Any | None, skill_id: str) -> Any | None:
    for entry in getattr(catalog, "entries", ()) if catalog is not None else ():
        if getattr(entry, "skill_id", None) == skill_id:
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
