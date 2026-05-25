# Native ASGI Migration Plan

## Goal

Move Marvex from WSGI compatibility bridges to native ASGI endpoint ownership without changing the public loopback API contract. The migration must preserve Assistant OS boundaries: Core owns turn execution, Control Plane owns safe inspection/control APIs, and host adapters own HTTP server/runtime mechanics.

## Current State

- Core and Control Plane run under Uvicorn on the existing two-port contract: Core API on `127.0.0.1:8765`, Control Plane on `127.0.0.1:8766`.
- Core API product routes are native FastAPI/ASGI on the default service host: `GET /health`, `GET /version`, `POST /v1/turns`, and `GET /v1/traces/{trace_id}`.
- Control Plane APIs dispatch through `ControlPlaneRuntime` from native FastAPI routes. `/control/state/stream` remains an explicit native SSE route, and non-`/control` SPA/static serving is native ASGI.
- The `a2wsgi` runtime dependency, WSGI factories, WSGI middleware bridge, `wsgiref` runner path, and WSGI compatibility tests are removed from runtime code.
- Browser Control Plane auth uses a shell-requested one-time claim URL and HttpOnly SameSite cookie. Bearer auth remains valid for privileged Rust/local callers.

## Migration Phases

1. Control Plane state/SSE boundary.
   - Status: implemented.
   - Native routes: `GET /control/state`, `GET /control/state/stream`.
   - No WSGI fallback remains.

2. Control Plane browser-session and session metadata APIs.
   - Status: implemented.
   - Native routes: `POST /control/browser-session/leases`, `GET /control/browser-session/claim`, `GET /control/sessions`, `POST /control/sessions`.
   - Uses the shared `BrowserSessionManager` and `BackendSessionCoordinator`.
   - Preserves one-time claim semantics, cookie attributes, safe session projections, and no-transcript persistence.

3. Control Plane read-only inspection APIs.
   - Status: implemented.
   - Native routes include health, version, snapshot, runtime execution, trace search, policies, logs, diagnostics, connectors, sources, autofetch, memory tree, marketplace browse, agent/persona projections, and voice status/read endpoints.
   - Keep response envelopes and safe-projection filtering unchanged.
   - Keep side-effecting endpoints WSGI until approval and mutation flows are migrated together.

4. Control Plane mutation and approval APIs.
   - Status: implemented.
   - Moved approvals, runtime-policy updates, marketplace enable/disable/proposals, memory forget, source forget, dependency installs, voice start/stop/config/download/test commands, and feedback/learning actions.
   - Preserve policy gating, explicit command semantics, and safe error envelopes.
   - Add route-level tests for malformed payloads, unauthorized requests, and policy-blocked operations before deleting WSGI equivalents.

5. Core API native ASGI boundary.
   - Status: implemented for the product Uvicorn host.
   - Native routes: `GET /health`, `GET /version`, `GET /v1/traces/{trace_id}`, and `POST /v1/turns`.
   - Manual/dev runner paths use the ASGI app through the Uvicorn host seam.

6. Remove WSGI bridge.
   - Status: implemented.
   - Remaining WSGI app factories and host compatibility surfaces are deleted.
   - Boundary gates reject WSGI middleware/factories and `wsgiref` runtime imports.

## Per-Slice Rules

- Move one ownership boundary at a time; do not rewrite unrelated routes opportunistically.
- Keep route paths, methods, status codes, response JSON, auth behavior, and token redaction unchanged unless a contract change is explicitly approved.
- Keep FastAPI/Uvicorn out of `services.core`; service composition may pass ASGI apps through host seams but must not own framework APIs.
- Keep maintained dependencies behind adapters. Do not add another HTTP framework or IPC library without a library-decision record and boundary gate update.
- Keep WSGI fallback routes until the corresponding native route has focused tests, service-entrypoint wiring tests, boundary-gate coverage, and packaged-runtime smoke coverage when relevant.

## Required Verification Per Phase

- Focused Python route tests for auth, success payloads, error envelopes, and streaming/cleanup behavior where applicable.
- Core service entrypoint tests proving shared runtime objects are wired once and reused by both Core and Control Plane.
- Boundary checks: `uv run python scripts/check_local_api_boundaries.py` and `uv run python scripts/check_control_plane_boundaries.py`.
- Runtime checks: `uv run pytest` and `uv run python scripts/run_all_checks.py`.
- Packaged smoke when route ownership affects service startup, Control Plane browser auth, sessions, state streaming, `/v1/turns`, or resource paths.
