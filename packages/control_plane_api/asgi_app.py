from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from a2wsgi import WSGIMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from packages.contracts import ErrorCode, ErrorEnvelope
from packages.local_api.auth_policy import validate_local_bearer_token
from packages.session_runtime import BackendSessionCoordinator

from .browser_session import BrowserSessionManager
from .state import (
    ACTIVE_STATUSES,
    SSE_ACTIVE_INTERVAL_SECONDS,
    SSE_HEARTBEAT_INTERVAL_SECONDS,
    state_snapshot_event,
    state_sse_frame,
)


SCHEMA_VERSION = "1"


def create_control_plane_asgi_app(
    *,
    control_wsgi_app: Any,
    local_auth_token: str,
    state_bus: Any | None,
    browser_session_manager: BrowserSessionManager,
    session_coordinator: BackendSessionCoordinator | None = None,
    title: str = "Marvex Control Plane",
) -> FastAPI:
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=None)
    sessions = session_coordinator or BackendSessionCoordinator()

    @app.get("/control/browser-session/claim", response_model=None)
    async def browser_session_claim(request: Request) -> Response:
        session = browser_session_manager.claim(request.query_params.get("claim"))
        if session is None:
            return JSONResponse(status_code=401, content=_auth_error("invalid_browser_session_claim"))
        return JSONResponse(
            status_code=302,
            content={},
            headers={
                "Set-Cookie": browser_session_manager.cookie_header(session),
                "Location": "/",
            },
        )

    @app.post("/control/browser-session/leases", response_model=None)
    async def browser_session_lease(request: Request) -> Response:
        auth_response = _auth_response(
            request=request,
            local_auth_token=local_auth_token,
            browser_session_manager=browser_session_manager,
        )
        if auth_response is not None:
            return auth_response
        return JSONResponse(browser_session_manager.create_lease())

    @app.get("/control/sessions", response_model=None)
    async def control_sessions(request: Request) -> Response:
        auth_response = _auth_response(
            request=request,
            local_auth_token=local_auth_token,
            browser_session_manager=browser_session_manager,
        )
        if auth_response is not None:
            return auth_response
        session_payloads = [handle.safe_projection() for handle in sessions.list_sessions()]
        return JSONResponse(
            {
                "schema_version": SCHEMA_VERSION,
                "sessions": session_payloads,
                "session_count": len(session_payloads),
                "transcript_persisted": False,
            }
        )

    @app.post("/control/sessions", response_model=None)
    async def create_control_session(request: Request) -> Response:
        auth_response = _auth_response(
            request=request,
            local_auth_token=local_auth_token,
            browser_session_manager=browser_session_manager,
        )
        if auth_response is not None:
            return auth_response
        handle = sessions.create_session(title=await _parse_session_title(request))
        return JSONResponse(
            {
                "schema_version": SCHEMA_VERSION,
                "session": handle.safe_projection(),
                "transcript_persisted": False,
            }
        )

    @app.get("/control/health", response_model=None)
    async def control_health(request: Request) -> Response:
        auth_response = _auth_response(
            request=request,
            local_auth_token=local_auth_token,
            browser_session_manager=browser_session_manager,
        )
        if auth_response is not None:
            return auth_response
        return JSONResponse({"schema_version": SCHEMA_VERSION, "status": "ok"})

    @app.get("/control/version", response_model=None)
    async def control_version(request: Request) -> Response:
        auth_response = _auth_response(
            request=request,
            local_auth_token=local_auth_token,
            browser_session_manager=browser_session_manager,
        )
        if auth_response is not None:
            return auth_response
        return JSONResponse({"schema_version": SCHEMA_VERSION, "service": "marvex-control-plane-api"})

    @app.get("/control/state", response_model=None)
    async def control_state(request: Request) -> Response:
        auth_response = _auth_response(
            request=request,
            local_auth_token=local_auth_token,
            browser_session_manager=browser_session_manager,
        )
        if auth_response is not None:
            return auth_response
        return JSONResponse(state_snapshot_event(state_bus=state_bus).model_dump(mode="json"))

    @app.get("/control/state/stream", response_model=None)
    async def control_state_stream(request: Request) -> Response:
        auth_response = _auth_response(
            request=request,
            local_auth_token=local_auth_token,
            browser_session_manager=browser_session_manager,
        )
        if auth_response is not None:
            return auth_response
        return StreamingResponse(
            iter_state_sse_frames(state_bus=state_bus),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    app.mount("/", WSGIMiddleware(control_wsgi_app))
    return app


async def _parse_session_title(request: Request) -> str | None:
    try:
        payload = await request.json()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("title")
    return value if isinstance(value, str) and value.strip() else None


async def iter_state_sse_frames(
    *,
    state_bus: Any | None,
    heartbeat_interval_seconds: float = SSE_HEARTBEAT_INTERVAL_SECONDS,
    active_interval_seconds: float = SSE_ACTIVE_INTERVAL_SECONDS,
) -> AsyncIterator[str]:
    has_subscribe = state_bus is not None and hasattr(state_bus, "subscribe")
    has_unsubscribe = state_bus is not None and hasattr(state_bus, "unsubscribe")
    event_q: asyncio.Queue[Any] = asyncio.Queue(maxsize=128)
    loop = asyncio.get_running_loop()

    def _enqueue(event: Any) -> None:
        if event_q.full():
            return
        event_q.put_nowait(event)

    def _on_event(event: Any) -> None:
        try:
            loop.call_soon_threadsafe(_enqueue, event)
        except RuntimeError:
            pass

    if has_subscribe:
        state_bus.subscribe(_on_event)

    try:
        yield state_sse_frame(state_snapshot_event(state_bus=state_bus))
        while True:
            snap = state_snapshot_event(state_bus=state_bus)
            timeout = active_interval_seconds if snap.status in ACTIVE_STATUSES else heartbeat_interval_seconds
            try:
                event = await asyncio.wait_for(event_q.get(), timeout=timeout)
                yield state_sse_frame(event)
            except asyncio.TimeoutError:
                yield state_sse_frame(state_snapshot_event(state_bus=state_bus))
    finally:
        if has_unsubscribe:
            state_bus.unsubscribe(_on_event)


def _auth_response(
    *,
    request: Request,
    local_auth_token: str,
    browser_session_manager: BrowserSessionManager,
) -> JSONResponse | None:
    auth_error = validate_local_bearer_token(
        authorization_header=request.headers.get("authorization"),
        expected_token=local_auth_token,
        trace_id="trace-control-plane-auth-required",
    )
    if auth_error is None:
        return None
    if browser_session_manager.validate_cookie_header(request.headers.get("cookie")):
        return None
    return JSONResponse(status_code=401, content=auth_error.model_dump(mode="json"))


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
