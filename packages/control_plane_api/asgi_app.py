from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from a2wsgi import WSGIMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from packages.local_api.auth_policy import validate_local_bearer_token

from .browser_session import BrowserSessionManager
from .state import (
    ACTIVE_STATUSES,
    SSE_ACTIVE_INTERVAL_SECONDS,
    SSE_HEARTBEAT_INTERVAL_SECONDS,
    state_snapshot_event,
    state_sse_frame,
)


def create_control_plane_asgi_app(
    *,
    control_wsgi_app: Any,
    local_auth_token: str,
    state_bus: Any | None,
    browser_session_manager: BrowserSessionManager,
    title: str = "Marvex Control Plane",
) -> FastAPI:
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=None)

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
