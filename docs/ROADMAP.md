# Roadmap

## Phase 0: Planning Only

Create docs, templates, validation scripts, diagrams, and placeholder folders. No product implementation.

## Phase 1: V1 Foundation

After docs are accepted:

- contracts only
- fake provider
- minimal Core Service
- telemetry lifecycle
- LM Studio Responses provider
- CLI vertical slice

## Phase 2: Process Readiness

- health and version endpoints
- subprocess startup and shutdown conventions
- JSON-RPC-style worker contracts
- supervisor research and decision

## Phase 3: Future Modules

Only after contracts:

- Intent Worker
- Tool Worker
- Memory
- Desktop Agent
- Voice Worker
- UI Shell
- Vision
- Proactive behavior

Frontend surfaces remain future-only until `docs/FRONTEND_BOUNDARY.md` is paired
with separate approved HTTP/WebSocket contracts and implementation task specs.
The frontend boundary document is not permission to implement a web UI, native
orb, presence shell, API server, or WebSocket server.

## Rule

The roadmap is not permission to implement. Each phase requires `accepted_docs: true`, approved contracts, real task spec files, and validation.

The provider turn is not the assistant turn. Future modules must pass the
Assistant Turn Spine gate in `docs/ASSISTANT_TURN_SPINE.md` before
implementation.
