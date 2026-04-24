# Library Policy

Marvex must avoid custom overcoding. If a mature, maintained, ready library exists, prefer using it instead of AI-generating a custom implementation.

Agents must verify current library choices in 2026 before recommending them. Use official documentation or maintained GitHub repositories only.

## Required Library Decision Fields

Every dependency recommendation must include:

- library name
- official source
- maintenance status
- why use it
- why not custom code
- fallback if abandoned

## Required Research Areas

Before implementing custom code, check for maintained libraries for:

- OpenAI-compatible clients and Responses API clients
- LM Studio integration
- JSON-RPC and FastAPI server support
- WebSocket communication
- structured logging
- config management
- process supervision
- plugin loading
- tool execution sandboxing
- SQLite and memory storage
- vector search if needed later
- MCP support
- STT and TTS wrappers if useful later

## Library Rules

- Do not AI-code custom SDKs if a maintained SDK exists.
- Do not wrap a library so heavily that the wrapper becomes a second SDK.
- Do not add a dependency without a library decision document.
- Do not rely on stale model knowledge for dependency status.
- Do not use random blog posts as authority.

## Fallback Rule

Every external dependency must have a fallback plan:

- replace with another maintained library
- isolate behind an adapter
- remove feature if nonessential
- implement only after an RFC if no maintained option exists

