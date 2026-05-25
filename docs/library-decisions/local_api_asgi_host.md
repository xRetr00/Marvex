# Local API ASGI Host Library Decision

library name: FastAPI
official source: https://fastapi.tiangolo.com/
maintenance status: active; release notes show current 2026 releases and Python 3.10+ support.
why use it: FastAPI gives Marvex an ASGI-native app boundary for local service hosting while endpoint ownership migrates one route group at a time. Core API routes and the migrated Control Plane routes now run as native FastAPI handlers.
why not custom code: A custom ASGI framework or socket loop would duplicate maintained request lifecycle, lifespan, and middleware behavior and would distract from Assistant OS boundaries.
fallback if abandoned: Keep the host adapter isolated and replace FastAPI with Starlette, Litestar, or another ASGI framework behind the host/control-plane adapter seams.
pyproject dependency: fastapi
declared dependency: fastapi>=0.135,<0.137

library name: a2wsgi
official source: https://github.com/abersheeran/a2wsgi
decision: removed from Marvex runtime dependencies.
why removed: The native-ASGI migration no longer needs a WSGI-to-ASGI middleware bridge. WSGI factories and compatibility tests have been deleted from runtime code.
fallback if needed again: Re-introduce a maintained WSGI adapter only behind `packages.local_api.asgi_host`, never inside Core business logic or frontend-owned paths.
pyproject dependency: none

library name: Uvicorn
official source: https://www.uvicorn.org/
maintenance status: active; PyPI release history shows 0.47.0 released in May 2026.
why use it: Uvicorn provides the maintained ASGI server loop for concurrent Core API and Control Plane service hosting on loopback.
why not custom code: Building a local async HTTP server would create security, shutdown, and concurrency risks better handled by a maintained ASGI server.
fallback if abandoned: Keep `packages.local_api.asgi_host` as the only server adapter and swap to Hypercorn or another ASGI server without changing Core or frontend contracts.
pyproject dependency: uvicorn
declared dependency: uvicorn==0.47.0
