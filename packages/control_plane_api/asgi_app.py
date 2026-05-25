from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from .runtime import ControlPlaneRuntime
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
    runtime: ControlPlaneRuntime,
    web_dist: str | None = None,
    title: str = "Marvex Control Plane",
) -> FastAPI:
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/control/state/stream", response_model=None)
    async def control_state_stream(request: Request) -> Response:
        auth_error = runtime.auth_error(
            authorization_header=request.headers.get("authorization"),
            cookie_header=request.headers.get("cookie"),
        )
        if auth_error is not None:
            return JSONResponse(status_code=401, content=auth_error)
        return StreamingResponse(
            iter_state_sse_frames(state_bus=runtime.state_bus),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], response_model=None)
    async def control_route(path: str, request: Request) -> Response:
        static_response = _static_response(path=f"/{path}", method=request.method, web_dist=web_dist)
        if static_response is not None:
            return static_response
        return await _runtime_response(runtime, request, path=f"/{path}")

    @app.api_route("/", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], response_model=None)
    async def control_root(request: Request) -> Response:
        static_response = _static_response(path="/", method=request.method, web_dist=web_dist)
        if static_response is not None:
            return static_response
        return await _runtime_response(runtime, request, path="/")

    return app


def _static_response(*, path: str, method: str, web_dist: str | None) -> FileResponse | None:
    if method.upper() != "GET" or path.startswith("/control") or not web_dist:
        return None

    from .static_web import resolve_static_file

    resolved, content_type = resolve_static_file(Path(web_dist), path)
    if resolved is None or not resolved.is_file():
        return None
    return FileResponse(resolved, media_type=content_type)


async def _runtime_response(runtime: ControlPlaneRuntime, request: Request, *, path: str) -> Response:
    body = await request.body()
    response = runtime.dispatch(
        method=request.method,
        path=path,
        query_string=request.url.query,
        headers={name.lower(): value for name, value in request.headers.items()},
        body=body,
    )
    status_code = int(response.status.split(" ", 1)[0])
    return JSONResponse(
        status_code=status_code,
        content=response.payload,
        headers=dict(response.headers),
    )


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


