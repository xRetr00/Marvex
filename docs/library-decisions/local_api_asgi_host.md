# Local API ASGI Host Library Decision

library name: FastAPI
official source: https://fastapi.tiangolo.com/
maintenance status: active; release notes show current 2026 releases and Python 3.10+ support.
why use it: FastAPI gives Marvex an ASGI-native app boundary for local service hosting while endpoint ownership migrates one route group at a time. The current native route ownership is limited to Control Plane state/SSE; Core and the remaining Control Plane routes still use compatibility adapters.
why not custom code: A custom ASGI framework or socket loop would duplicate maintained request lifecycle, lifespan, and middleware behavior and would distract from Assistant OS boundaries.
fallback if abandoned: Keep existing WSGI app contracts and replace the thin host adapter with Starlette, Litestar, or another ASGI adapter behind the host/control-plane adapter seams.
pyproject dependency: fastapi
declared dependency: fastapi>=0.135,<0.137

library name: a2wsgi
official source: https://github.com/abersheeran/a2wsgi
maintenance status: active enough for this compatibility seam; PyPI release history shows 1.10.10 released in June 2025.
why use it: FastAPI recommends a2wsgi for mounting WSGI applications, and it replaces Starlette's deprecated WSGI middleware while Marvex migrates endpoint ownership deliberately.
why not custom code: A custom WSGI-to-ASGI adapter would duplicate protocol translation, thread-pool execution, backpressure, and streaming behavior that belongs in a maintained boundary adapter.
fallback if abandoned: Keep the adapter isolated at the ASGI boundary and replace remaining WSGI routes with native ASGI endpoints or another maintained WSGI-to-ASGI bridge without changing Core or frontend contracts.
pyproject dependency: a2wsgi
declared dependency: a2wsgi>=1.10.10,<2

library name: Uvicorn
official source: https://www.uvicorn.org/
maintenance status: active; PyPI release history shows 0.47.0 released in May 2026.
why use it: Uvicorn provides the maintained ASGI server loop for concurrent Core API and Control Plane service hosting on loopback.
why not custom code: Building a local async HTTP server would create security, shutdown, and concurrency risks better handled by a maintained ASGI server.
fallback if abandoned: Keep `packages.local_api.asgi_host` as the only server adapter and swap to Hypercorn or another ASGI server without changing Core or frontend contracts.
pyproject dependency: uvicorn
declared dependency: uvicorn==0.47.0
