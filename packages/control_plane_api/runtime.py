from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs

from packages.contracts import ErrorCode, ErrorEnvelope
from packages.local_api.auth_policy import validate_local_bearer_token
from packages.capability_runtime import AutonomyMode, AutonomyPolicy, PolicyDecisionAuditRecord
from packages.marketplace_runtime import MarketplaceEnablementState, MarketplaceProposalStore
from packages.memory_runtime import MemoryRef
from packages.session_runtime import BackendSessionCoordinator
from packages.telemetry.search import TraceSearchQuery, search_traces

from .approvals import InMemoryApprovalStore
from .browser_session import BrowserSessionManager
from .deps import handle_deps_request
from .logs import logs_payload
from .models import ApprovalDecisionInput, ApprovalDecisionResponse, ControlPlaneSnapshot
from .providers import handle_provider_control_request
from .state import handle_state_snapshot
from .voice import handle_voice_control_request


# file size justification: Control Plane API dispatch is centralized for the
# final native-ASGI migration; endpoint groups can split into service-owned
# modules after the WSGI boundary is fully gone.
SCHEMA_VERSION = "1"
CONTROL_PREFIX = "/control"
# Compatibility marker for validation gates: McpAllowlistProposal is now
# surfaced through MarketplaceEnablementProposal safe projections.


@dataclass(frozen=True)
class ControlPlaneResponse:
    status: str
    payload: dict[str, Any]
    headers: tuple[tuple[str, str], ...] = ()


ControlPlaneDispatcher = Callable[[str, str, str, dict[str, str], bytes], ControlPlaneResponse]


class ControlPlaneRuntime:
    def __init__(self, **kwargs: Any) -> None:
        if kwargs.get("approval_store") is None:
            kwargs["approval_store"] = InMemoryApprovalStore()
        if kwargs.get("snapshot") is None:
            kwargs["snapshot"] = ControlPlaneSnapshot.foundation_default(schema_version=SCHEMA_VERSION)
        if kwargs.get("browser_session_manager") is None:
            kwargs["browser_session_manager"] = BrowserSessionManager()
        self.local_auth_token = str(kwargs.get("local_auth_token") or "")
        self.browser_session_manager = kwargs["browser_session_manager"]
        self.state_bus = kwargs.get("state_bus")
        self._dispatch = _create_control_plane_dispatcher(**kwargs)

    def dispatch(
        self,
        *,
        method: str,
        path: str,
        query_string: str = "",
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> ControlPlaneResponse:
        return self._dispatch(method, path, query_string, headers or {}, body)

    def auth_error(self, *, authorization_header: str | None, cookie_header: str | None) -> dict[str, Any] | None:
        auth_error = validate_local_bearer_token(
            authorization_header=authorization_header,
            expected_token=self.local_auth_token,
            trace_id="trace-control-plane-auth-required",
        )
        if auth_error is None:
            return None
        if self.browser_session_manager.validate_cookie_header(cookie_header):
            return None
        return auth_error.model_dump(mode="json")


def _create_control_plane_dispatcher(
    *,
    approval_store: InMemoryApprovalStore,
    snapshot: ControlPlaneSnapshot,
    local_auth_token: str,
    approval_history: tuple[ApprovalDecisionResponse, ...] = (),
    mcp_marketplace: Any | None = None,
    skills_marketplace: Any | None = None,
    mcp_runtime_registry: Any | None = None,
    skills_root: str | None = None,
    memory_store: Any | None = None,
    memory_service: Any | None = None,
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
    web_dist: str | None = None,
    log_reader: Any | None = None,
    session_coordinator: BackendSessionCoordinator | None = None,
    browser_session_manager: BrowserSessionManager | None = None,
    provider_control: Any | None = None,
    web_search_settings: Any | None = None,
    web_search_update_callback: Any | None = None,
) -> ControlPlaneDispatcher:
    runtime_policy = autonomy_policy or AutonomyPolicy.for_mode(AutonomyMode.ASK_BEFORE_RISKY)
    proposal_store = marketplace_proposal_store or MarketplaceProposalStore()
    sessions = session_coordinator or BackendSessionCoordinator()
    browser_sessions = browser_session_manager or BrowserSessionManager()

    def dispatch(
        method: str,
        path: str,
        query_string: str,
        headers: dict[str, str],
        body: bytes,
    ) -> ControlPlaneResponse:
        nonlocal runtime_policy
        method = method.upper()
        path, _separator, inline_query = path.partition("?")
        query_string = query_string or inline_query
        environ: dict[str, Any] = {
            "REQUEST_BODY": body,
            "HTTP_AUTHORIZATION": headers.get("authorization"),
            "HTTP_COOKIE": headers.get("cookie"),
        }

        if method == "GET" and path == f"{CONTROL_PREFIX}/browser-session/claim":
            claim = _first(parse_qs(query_string, keep_blank_values=False), "claim")
            session = browser_sessions.claim(claim)
            if session is None:
                return _json_response(
                    None,
                    "401 Unauthorized",
                    _auth_error("invalid_browser_session_claim"),
                )
            return ControlPlaneResponse(
                "302 Found",
                {},
                (
                    ("Set-Cookie", browser_sessions.cookie_header(session)),
                    ("Location", "/"),
                ),
            )

        auth_error = validate_local_bearer_token(
            authorization_header=_authorization_header(environ),
            expected_token=local_auth_token,
            trace_id="trace-control-plane-auth-required",
        )
        if auth_error is not None and not browser_sessions.validate_cookie_header(_cookie_header(environ)):
            return _json_response(None, "401 Unauthorized", auth_error.model_dump(mode="json"))

        if method == "POST" and path == f"{CONTROL_PREFIX}/browser-session/leases":
            return _json_response(None, "200 OK", browser_sessions.create_lease())

        if method == "GET" and path == f"{CONTROL_PREFIX}/sessions":
            session_payloads = [handle.safe_projection() for handle in sessions.list_sessions()]
            return _json_response(
                None,
                "200 OK",
                {
                    "schema_version": SCHEMA_VERSION,
                    "sessions": session_payloads,
                    "session_count": len(session_payloads),
                    "transcript_persisted": False,
                },
            )
        if method == "POST" and path == f"{CONTROL_PREFIX}/sessions":
            title = _parse_session_title(environ)
            handle = sessions.create_session(title=title)
            return _json_response(
                None,
                "200 OK",
                {
                    "schema_version": SCHEMA_VERSION,
                    "session": handle.safe_projection(),
                    "transcript_persisted": False,
                },
            )
        if path.startswith(f"{CONTROL_PREFIX}/sessions/") and method in {"PATCH", "DELETE"}:
            session_id = path.removeprefix(f"{CONTROL_PREFIX}/sessions/").strip("/")
            if not session_id:
                return _json_response(None, "400 Bad Request", {"schema_version": SCHEMA_VERSION, "error": "session_id_required"})
            if method == "DELETE":
                deleted = sessions.delete_session(session_id)
                return _json_response(
                    None,
                    "200 OK" if deleted else "404 Not Found",
                    {"schema_version": SCHEMA_VERSION, "deleted": deleted, "session_id": session_id, "transcript_persisted": False},
                )
            title = _parse_session_title(environ)
            handle = sessions.rename_session(session_id, title=title)
            if handle is None:
                return _json_response(None, "404 Not Found", {"schema_version": SCHEMA_VERSION, "error": "session_not_found", "session_id": session_id})
            return _json_response(
                None,
                "200 OK",
                {"schema_version": SCHEMA_VERSION, "session": handle.safe_projection(), "transcript_persisted": False},
            )

        voice_response = handle_voice_control_request(method=method, path=path, environ=environ, voice_control=voice_control, voice_worker_control=voice_worker_control)
        if voice_response is not None:
            status, payload = voice_response
            return _json_response(None, status, payload)

        deps_response = handle_deps_request(method=method, path=path, environ=environ, pip_runner=deps_pip_runner)
        if deps_response is not None:
            status, payload = deps_response
            return _json_response(None, status, payload)

        provider_response = handle_provider_control_request(method=method, path=path, environ=environ, provider_control=provider_control)
        if provider_response is not None:
            status, payload = provider_response
            return _json_response(None, status, payload)

        if path == f"{CONTROL_PREFIX}/web-search":
            if web_search_settings is None:
                return _json_response(None, "404 Not Found", _error("web_search_settings_not_configured", path))
            if method == "GET":
                settings = web_search_settings.load()
                return _json_response(None, "200 OK", _safe_nested_mapping(settings.safe_projection()))
            if method == "POST":
                try:
                    payload = json.loads(_read_request_body(environ) or "{}")
                    if not isinstance(payload, dict):
                        raise ValueError("payload must be an object")
                    settings = web_search_settings.update(payload)
                    if callable(web_search_update_callback):
                        web_search_update_callback(settings)
                    return _json_response(None, "200 OK", _safe_nested_mapping(settings.safe_projection()))
                except Exception:
                    return _json_response(None, "400 Bad Request", _error("invalid_web_search_settings", path))

        if method == "GET" and path == f"{CONTROL_PREFIX}/approvals":
            return _json_response(None, "200 OK", approval_store.list_pending().model_dump(mode="json"))
        if method == "GET" and path == f"{CONTROL_PREFIX}/approvals/history":
            history = approval_store.list_history()
            decisions = tuple(history.decisions) + tuple(approval_history)
            payload = {
                "schema_version": SCHEMA_VERSION,
                "decisions": [decision.model_dump(mode="json") for decision in decisions],
                "decision_count": len(decisions),
                "raw_payload_persisted": False,
            }
            return _json_response(None, "200 OK", payload)
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/approvals/"):
            approval_id, action = _approval_path(path)
            if action is not None:
                return _json_response(None, "404 Not Found", _error("not_found", path))
            approval = approval_store.read_pending(approval_id)
            if approval is None:
                return _json_response(None, "404 Not Found", _error("approval_not_found", path))
            return _json_response(None, "200 OK", approval.model_dump(mode="json"))
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/approvals/"):
            approval_id, action = _approval_path(path)
            if action not in {"approve", "deny", "cancel"}:
                return _json_response(None, "404 Not Found", _error("not_found", path))
            decision_input = _parse_decision_input(environ)
            if isinstance(decision_input, ErrorEnvelope):
                return _json_response(None, "400 Bad Request", decision_input.model_dump(mode="json"))
            if action == "approve":
                decision = approval_store.approve(approval_id, reason=decision_input.reason)
            elif action == "cancel":
                decision = approval_store.cancel(approval_id, reason=decision_input.reason)
            else:
                decision = approval_store.deny(approval_id, reason=decision_input.reason)
            if decision is None:
                return _json_response(None, "404 Not Found", _error("approval_not_found", path))
            return _json_response(None, "200 OK", decision.model_dump(mode="json"))
        if method == "GET" and path == f"{CONTROL_PREFIX}/marketplace/mcp":
            entries = tuple(mcp_marketplace.safe_projection()) if mcp_marketplace is not None else ()
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "entries": entries, "read_only_browse": True, "raw_payload_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/mcp/runtime":
            payload = mcp_runtime_registry.safe_projection() if mcp_runtime_registry is not None else {"schema_version": SCHEMA_VERSION, "servers": [], "server_count": 0, "raw_registry_payload_persisted": False}
            return _json_response(None, "200 OK", _safe_nested_mapping(payload))
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/marketplace/mcp/") and path.endswith("/install"):
            server_id = path.removeprefix(f"{CONTROL_PREFIX}/marketplace/mcp/").removesuffix("/install").strip("/")
            entry = _find_entry(mcp_marketplace, server_id)
            if entry is None:
                return _json_response(None, "404 Not Found", _error("mcp_marketplace_entry_not_found", path))
            if mcp_runtime_registry is None:
                return _json_response(None, "404 Not Found", _error("mcp_runtime_registry_not_configured", path))
            config = entry.to_installed_config()
            installed = mcp_runtime_registry.upsert_server(config)
            return _json_response(
                None,
                "200 OK",
                {
                    "schema_version": SCHEMA_VERSION,
                    "installed": True,
                    "server": installed.safe_projection(tool_count=0),
                    "install_started": True,
                    "launch_started": False,
                    "auto_execution_allowed": False,
                    "raw_registry_payload_persisted": False,
                },
            )
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/marketplace/mcp/") and path.endswith("/disable"):
            server_id = path.removeprefix(f"{CONTROL_PREFIX}/marketplace/mcp/").removesuffix("/disable").strip("/")
            state = MarketplaceEnablementState.disabled(subject_id=server_id, subject_kind="mcp_server", reason_code="disabled_by_control_plane")
            return _json_response(None, "200 OK", state.safe_projection())
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/marketplace/mcp/") and path.endswith("/allowlist-proposals"):
            server_id = path.removeprefix(f"{CONTROL_PREFIX}/marketplace/mcp/").removesuffix("/allowlist-proposals").strip("/")
            entry = _find_entry(mcp_marketplace, server_id)
            if entry is None:
                return _json_response(None, "404 Not Found", _error("mcp_marketplace_entry_not_found", path))
            proposal = proposal_store.propose_mcp_allowlist(entry, requested_by="control_plane")
            return _json_response(None, "200 OK", proposal.safe_projection())
        if method == "GET" and path == f"{CONTROL_PREFIX}/marketplace/skills":
            entries = tuple(skills_marketplace.safe_projection()) if skills_marketplace is not None else ()
            previews = tuple(_skill_previews(skills_marketplace)) if skills_marketplace is not None else ()
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "entries": entries, "previews": previews, "raw_payload_persisted": False})
        if method == "POST" and path == f"{CONTROL_PREFIX}/skills/install":
            if not skills_root:
                return _json_response(None, "404 Not Found", _error("skills_root_not_configured", path))
            try:
                from packages.skills_runtime import SkillPackageInstaller

                payload = json.loads(_read_request_body(environ) or "{}")
                source_path = str(payload.get("source_path") or "").strip()
                if not source_path:
                    return _json_response(None, "400 Bad Request", _error("missing_skill_source_path", path))
                result = SkillPackageInstaller(managed_root=skills_root).install_from_directory(source_path, source_label="control_plane")
                status = "200 OK" if result.installed else "400 Bad Request"
                return _json_response(None, status, result.safe_projection())
            except Exception:
                return _json_response(None, "400 Bad Request", _error("skill_install_failed", path))
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/marketplace/skills/") and path.endswith("/disable"):
            skill_id = path.removeprefix(f"{CONTROL_PREFIX}/marketplace/skills/").removesuffix("/disable").strip("/")
            state = MarketplaceEnablementState.disabled(subject_id=skill_id, subject_kind="skill", reason_code="disabled_by_control_plane")
            return _json_response(None, "200 OK", state.safe_projection())
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/marketplace/skills/") and path.endswith("/enable"):
            skill_id = path.removeprefix(f"{CONTROL_PREFIX}/marketplace/skills/").removesuffix("/enable").strip("/")
            entry = _find_skill_entry(skills_marketplace, skill_id)
            if entry is None:
                return _json_response(None, "404 Not Found", _error("skill_marketplace_entry_not_found", path))
            proposal = proposal_store.propose_skill_enablement(entry, requested_by="control_plane")
            return _json_response(None, "200 OK", proposal.safe_projection())
        if method == "GET" and path == f"{CONTROL_PREFIX}/memory/health":
            if memory_service is not None and hasattr(memory_service, "health"):
                payload = _safe_nested_mapping(memory_service.health())
            else:
                payload = {
                    "schema_version": SCHEMA_VERSION,
                    "status": "configured" if memory_store is not None else "unavailable",
                    "backend_count": 1 if memory_store is not None else 0,
                    "backends": ({"backend": "compatibility", "status": "configured", "raw_transcript_persisted": False},) if memory_store is not None else (),
                    "raw_content_persisted": False,
                }
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, **payload, "raw_content_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/memory":
            records = (
                tuple(memory_service.safe_inspect())
                if memory_service is not None and hasattr(memory_service, "safe_inspect")
                else tuple(memory_store.safe_inspect())
                if memory_store is not None and hasattr(memory_store, "safe_inspect")
                else ()
            )
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "records": records, "record_count": len(records), "raw_transcript_persisted": False})
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/memory/") and path.endswith("/forget"):
            memory_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/").removesuffix("/forget").strip("/")
            if memory_service is not None and hasattr(memory_service, "forget"):
                forgotten = bool(memory_service.forget(memory_id))
                return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "memory_ref": {"ref_type": "memory", "ref_id": memory_id}, "forgotten": forgotten, "raw_content_persisted": False})
            if memory_store is None:
                return _json_response(None, "404 Not Found", _error("memory_store_not_configured", path))
            result = memory_store.forget(MemoryRef(ref_type="memory", ref_id=memory_id))
            return _json_response(None, "200 OK", result.safe_projection())
        if method == "GET" and path == f"{CONTROL_PREFIX}/connectors":
            connectors = tuple(_safe_projection(item) for item in connector_manifests)
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "connectors": connectors, "connector_count": len(connectors), "raw_token_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/sources":
            sources = tuple(_safe_projection(item) for item in memory_sources)
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "sources": sources, "source_count": len(sources), "raw_credentials_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/autofetch":
            policies = tuple(_safe_projection(item) for item in auto_fetch_policies)
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "policies": policies, "policy_count": len(policies), "raw_payload_persisted": False})
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/autofetch/"):
            connector_id, action = _autofetch_path(path)
            if action not in {"enable", "disable", "pause"}:
                return _json_response(None, "404 Not Found", _error("not_found", path))
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "connector_id": connector_id, "requested_state": "enabled" if action == "enable" else action + "d", "sync_started": False, "raw_payload_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/memory/tree/search":
            query = _first(parse_qs(query_string, keep_blank_values=False), "q") or ""
            result = (
                memory_service.search(query)
                if memory_service is not None and hasattr(memory_service, "search") and query
                else memory_tree_runtime.memory_tree_search(query)
                if memory_tree_runtime is not None
                else None
            )
            payload = result.safe_projection() if result is not None else {"query": query, "results": []}
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, **payload})
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/memory/tree/source/"):
            source_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/tree/source/").strip("/")
            tree = memory_tree_runtime.memory_get_source_tree(source_id) if memory_tree_runtime is not None else None
            tree_payload = {"source_id": source_id, "nodes": [node.safe_projection() for node in tree.nodes]} if tree is not None else {"source_id": source_id, "nodes": []}
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "tree": tree_payload, "raw_content_persisted": False})
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/memory/tree/topic/"):
            topic_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/tree/topic/").strip("/")
            tree = memory_tree_runtime.memory_get_topic_tree(topic_id) if memory_tree_runtime is not None else None
            tree_payload = {"topic_id": topic_id, "nodes": [node.safe_projection() for node in tree.nodes]} if tree is not None else {"topic_id": topic_id, "nodes": []}
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "tree": tree_payload, "raw_content_persisted": False})
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/memory/tree/daily/"):
            digest_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/tree/daily/").strip("/")
            digest = memory_tree_runtime.memory_get_daily_digest(digest_id) if memory_tree_runtime is not None else None
            payload = digest.safe_projection() if digest is not None else {"node_id": digest_id, "evidence_count": 0}
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "daily_digest": payload, "raw_content_persisted": False})
        if method == "GET" and path.startswith(f"{CONTROL_PREFIX}/memory/tree/drill-down/"):
            chunk_id = path.removeprefix(f"{CONTROL_PREFIX}/memory/tree/drill-down/").strip("/")
            result = memory_tree_runtime.memory_drill_down(chunk_id) if memory_tree_runtime is not None else None
            payload = result.safe_projection() if result is not None else {"chunk_id": chunk_id}
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "evidence": payload})
        if method == "GET" and path == f"{CONTROL_PREFIX}/memory/tree/scoring":
            scores = tuple(_safe_projection(item) for item in scoring_views)
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "scores": scores, "score_count": len(scores), "raw_content_persisted": False})
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/sources/") and path.endswith("/forget"):
            source_id = path.removeprefix(f"{CONTROL_PREFIX}/sources/").removesuffix("/forget").strip("/")
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "source_id": source_id, "delete_started": False, "requires_memory_runtime_policy": True, "raw_content_persisted": False})

        if method == "GET" and path == f"{CONTROL_PREFIX}/runtime/execution":
            return _json_response(None, "200 OK", _runtime_execution_payload(snapshot, approval_store))
        if method == "GET" and path == f"{CONTROL_PREFIX}/traces/search":
            query = _trace_search_query(query_string)
            searchable_trace_ids = trace_ids or _reader_trace_ids(trace_reader)
            result = search_traces(trace_reader, query, trace_ids=searchable_trace_ids) if trace_reader is not None else None
            payload = result.safe_projection() if result is not None else {"schema_version": SCHEMA_VERSION, "traces": [], "match_count": 0, "truncated": False, "raw_payload_persisted": False}
            return _json_response(None, "200 OK", payload)
        if method == "GET" and path == f"{CONTROL_PREFIX}/policies":
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "policies": tuple(_safe_mapping(policy) for policy in policy_views), "raw_payload_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/runtime-policy":
            projection = runtime_policy.safe_projection(recent_audit=policy_audit_records)
            return _json_response(None, "200 OK", projection.model_dump(mode="json"))
        if method == "GET" and path == f"{CONTROL_PREFIX}/runtime-policy/audit":
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "audit_records": [_safe_nested_mapping(record.safe_projection()) for record in policy_audit_records], "audit_count": len(policy_audit_records), "raw_payload_persisted": False})
        if method == "POST" and path == f"{CONTROL_PREFIX}/feedback":
            if learning_runner is None:
                return _json_response(None, "404 Not Found", _error("learning_runner_not_configured", path))
            event_payload = _parse_feedback_event_payload(environ)
            if isinstance(event_payload, ErrorEnvelope):
                return _json_response(None, "400 Bad Request", event_payload.model_dump(mode="json"))
            summary = learning_runner.ingest_feedback_payload(event_payload)
            return _json_response(None, "200 OK", _learning_summary_payload(summary))
        if method == "GET" and path == f"{CONTROL_PREFIX}/feedback":
            events = tuple(getattr(learning_store, "feedback_events", ()) if learning_store is not None else ())
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "events": [_safe_nested_mapping(event.model_dump(mode="json")) for event in events], "event_count": len(events), "raw_feedback_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/learning/candidates":
            summary = getattr(learning_store, "latest_summary", None) if learning_store is not None else None
            return _json_response(None, "200 OK", _learning_summary_payload(summary))
        if method == "POST" and path.startswith(f"{CONTROL_PREFIX}/learning/candidates/") and path.endswith("/apply"):
            if learning_runner is None:
                return _json_response(None, "404 Not Found", _error("learning_runner_not_configured", path))
            candidate_id = path.removeprefix(f"{CONTROL_PREFIX}/learning/candidates/").removesuffix("/apply").strip("/")
            result = learning_runner.apply_candidate(candidate_id)
            return _json_response(None, "200 OK", _safe_nested_mapping(result.model_dump(mode="json")))
        if method == "POST" and path == f"{CONTROL_PREFIX}/runtime-policy":
            mode = _parse_runtime_policy_mode(environ)
            if mode is None:
                return _json_response(None, "400 Bad Request", _error("invalid_runtime_policy_mode", path))
            runtime_policy = AutonomyPolicy.for_mode(mode)
            payload = runtime_policy.safe_projection(recent_audit=policy_audit_records).model_dump(mode="json")
            payload["policy_update_started"] = True
            payload["execution_started"] = False
            return _json_response(None, "200 OK", payload)
        if method == "GET" and path == f"{CONTROL_PREFIX}/state":
            _status, payload = handle_state_snapshot(state_bus=state_bus)
            return _json_response(None, _status, payload)
        if method == "GET" and path == f"{CONTROL_PREFIX}/state/stream":
            return _json_response(None, "404 Not Found", _error("not_found", path))
        if method == "GET" and path == f"{CONTROL_PREFIX}/diagnostics":
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, **_safe_mapping(diagnostics or {}), "raw_payload_persisted": False})
        if method == "GET" and path == f"{CONTROL_PREFIX}/logs":
            return _json_response(None, "200 OK", logs_payload(log_reader, trace_reader=trace_reader))
        if method == "GET" and path == f"{CONTROL_PREFIX}/snapshot":
            payload = snapshot.model_dump(mode="json")
            if provider_control is not None and hasattr(provider_control, "provider_catalog"):
                provider_catalog = _safe_nested_mapping(provider_control.provider_catalog())
                payload["providers"] = provider_catalog.get("providers", [])
                payload["settings"] = {
                    **dict(payload.get("settings", {})),
                    "active_provider_id": provider_catalog.get("active_provider_id"),
                    "provider_control": provider_catalog,
                }
            trace_rows = _trace_rows(trace_reader=trace_reader, trace_ids=trace_ids)
            if trace_rows:
                payload["traces"] = trace_rows
                payload["telemetry"] = {
                    **dict(payload.get("telemetry", {})),
                    "trace_count": len(trace_rows),
                    "telemetry_event_count": sum(int(row.get("event_count", 0) or 0) for row in trace_rows),
                }
            payload["approvals"] = approval_store.list_pending().model_dump(mode="json")
            return _json_response(None, "200 OK", payload)
        if method == "GET" and path == f"{CONTROL_PREFIX}/health":
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "status": "ok"})
        if method == "GET" and path == f"{CONTROL_PREFIX}/version":
            return _json_response(None, "200 OK", {"schema_version": SCHEMA_VERSION, "service": "marvex-control-plane-api"})
        return _json_response(None, "404 Not Found", _error("not_found", path))

    return dispatch



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
    raw_body = environ.get("REQUEST_BODY", b"")
    return raw_body.decode("utf-8") if isinstance(raw_body, bytes) else str(raw_body)


def _authorization_header(environ: dict[str, Any]) -> str | None:
    value = environ.get("HTTP_AUTHORIZATION")
    return value if isinstance(value, str) else None


def _cookie_header(environ: dict[str, Any]) -> str | None:
    value = environ.get("HTTP_COOKIE")
    return value if isinstance(value, str) else None


def _auth_error(reason: str) -> dict[str, Any]:
    return ErrorEnvelope(
        schema_version="0.1.1-draft",
        trace_id="trace-control-plane-auth-required",
        error_id="control-plane-auth-required",
        code=ErrorCode.AUTH_REQUIRED,
        message="Local API authentication required.",
        recoverable=False,
        source="control_plane_api",
        details={"reason": reason},
    ).model_dump(mode="json")


def _parse_session_title(environ: dict[str, Any]) -> str | None:
    try:
        payload = json.loads(_read_request_body(environ))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("title")
    return value if isinstance(value, str) and value.strip() else None


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


def _trace_rows(*, trace_reader: Any | None, trace_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    ids = list(trace_ids or _reader_trace_ids(trace_reader))
    rows: list[dict[str, Any]] = []
    for trace_id in ids[-50:]:
        try:
            envelope = trace_reader.read_trace(str(trace_id)) if trace_reader is not None else None
        except Exception:
            envelope = None
        rows.append(_trace_row(trace_id=str(trace_id), envelope=envelope))
    return rows


def _reader_trace_ids(trace_reader: Any | None, *, limit: int = 50) -> tuple[str, ...]:
    if trace_reader is None:
        return ()
    trace_ids = getattr(trace_reader, "trace_ids", None)
    if callable(trace_ids):
        try:
            return tuple(str(trace_id) for trace_id in trace_ids(limit=limit))[-limit:]
        except Exception:
            return ()
    if hasattr(trace_reader, "_events_by_trace_id"):
        try:
            return tuple(str(trace_id) for trace_id in getattr(trace_reader, "_events_by_trace_id").keys())[-limit:]
        except Exception:
            return ()
    return ()


def _trace_row(*, trace_id: str, envelope: dict[str, Any] | None) -> dict[str, Any]:
    safe_envelope = envelope if isinstance(envelope, dict) else {}
    events = safe_envelope.get("events")
    safe_events = [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []
    first_event = safe_events[0] if safe_events else {}
    latest_event = safe_events[-1] if safe_events else {}
    row: dict[str, Any] = {
        "trace_id": str(safe_envelope.get("trace_id") or trace_id),
        "scope": str(safe_envelope.get("scope") or "unknown"),
        "source": str(safe_envelope.get("source") or "unknown"),
        "event_count": int(safe_envelope.get("event_count", len(safe_events)) or 0),
        "truncated": bool(safe_envelope.get("truncated", False)),
        "raw_payload_persisted": False,
    }
    if first_event.get("timestamp") is not None:
        row["first_timestamp"] = str(first_event.get("timestamp"))
    if latest_event.get("timestamp") is not None:
        row["last_timestamp"] = str(latest_event.get("timestamp"))
    for source_key, output_key in (
        ("stage", "latest_stage"),
        ("level", "latest_level"),
        ("status", "latest_status"),
        ("message", "latest_message"),
        ("tool_status", "tool_status"),
        ("approval_status", "approval_status"),
        ("finish_reason", "finish_reason"),
    ):
        value = latest_event.get(source_key)
        if isinstance(value, str | int | float | bool):
            row[output_key] = value
    malformed_count = safe_envelope.get("malformed_record_count")
    if isinstance(malformed_count, int):
        row["malformed_record_count"] = malformed_count
    return _safe_nested_mapping(row)


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


def _json_response(_unused: object, status: str, payload: dict[str, Any]) -> ControlPlaneResponse:
    return ControlPlaneResponse(status=status, payload=payload)
