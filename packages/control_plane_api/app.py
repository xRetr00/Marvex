from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from packages.contracts import ErrorCode, ErrorEnvelope
from packages.local_api.auth_policy import validate_local_bearer_token

from .approvals import InMemoryApprovalStore
from .models import ApprovalDecisionInput, ControlPlaneSnapshot


StartResponse = Any
WsgiApp = Any
SCHEMA_VERSION = "1"
CONTROL_PREFIX = "/control"


def create_control_plane_api_app(
    *,
    approval_store: InMemoryApprovalStore,
    snapshot: ControlPlaneSnapshot,
    local_auth_token: str,
) -> WsgiApp:
    def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        auth_error = validate_local_bearer_token(
            authorization_header=_authorization_header(environ),
            expected_token=local_auth_token,
            trace_id="trace-control-plane-auth-required",
        )
        if auth_error is not None:
            return _json_response(start_response, "401 Unauthorized", auth_error.model_dump(mode="json"))

        if method == "GET" and path == f"{CONTROL_PREFIX}/approvals":
            return _json_response(start_response, "200 OK", approval_store.list_pending().model_dump(mode="json"))
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


def _error(reason: str, path: str) -> dict[str, Any]:
    return ErrorEnvelope(
        schema_version="0.1.1-draft",
        trace_id="trace-control-plane-error",
        error_id="control-plane-error",
        code=ErrorCode.NOT_FOUND,
        message="Control Plane endpoint not found." if reason == "not_found" else "Control Plane approval not found.",
        recoverable=False,
        source="control_plane_api",
        details={"reason": reason, "path": path},
    ).model_dump(mode="json")


def _json_response(start_response: StartResponse, status: str, payload: dict[str, Any]) -> list[bytes]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body)))], None)
    return [body]