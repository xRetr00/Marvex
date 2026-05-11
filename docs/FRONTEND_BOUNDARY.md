# Frontend Boundary

Task 085 defines the frontend and UI boundary before real UI implementation.
This document is planning/spec only. It does not implement a web app, native
orb, presence shell, backend API, WebSocket server, provider integration, Core
integration, AssistantTurnRuntime integration, services, or product behavior.

## Boundary Decision

The web frontend is a client and presentation surface only.

Native Orb/Presence is a future shell and presence surface only.

Backend/Core remains the single source of truth for assistant state, provider
state, session state, policy outcomes, and runtime decisions.

UI code must not become backend logic. UI surfaces may render state, collect
input, request approved backend actions, and display backend-approved status
information. They must not own assistant runtime behavior.

## Forbidden UI Ownership

Future UI surfaces must not:

- call provider adapters directly
- select providers directly
- own session state
- own `previous_response_id` behavior
- own retry policy
- parse provider structured output
- execute tools
- write memory
- control the desktop directly
- make policy or permission decisions
- bypass Backend/Core contracts
- infer provider/model/status information from local implementation details

Provider/model/status information may be displayed only when the backend exposes
it through approved contracts.

## Mock And Prototype Rules

UI may use mock fixtures before a backend API exists, but those fixtures must be
clearly marked as mock data and must not be treated as backend contracts.

Static prototypes may be created only after separate task approval. Static
prototype approval does not authorize real backend integration, service runtime,
provider execution, tool execution, memory writes, desktop control, or product
behavior.

Real UI integration requires approved HTTP and/or WebSocket contracts before any
runtime connection is implemented.

## Future Allowed UI Surfaces

These surfaces are allowed as future concepts, not implemented behavior:

- Web UI
- Native Orb/Presence
- Trace/Event viewer
- Settings surface
- Voice/face visualization later

Each surface needs its own approved task spec before implementation.

## Future Communication Direction

Future UI-to-backend communication may include:

- submit user input
- request assistant/session state
- request settings changes after contract approval

Future backend-to-UI communication may include:

- assistant state events
- trace events
- final response
- provider status
- error envelope

No backend logic belongs inside UI clients.

## Draft Event And State Concepts

The following concepts are draft UI display states only. They are not approved
runtime states and are not implemented contracts:

- `idle`
- `listening`
- `thinking`
- `responding`
- `speaking`
- `tool_waiting` later
- `error`

Future tasks must decide whether these states become HTTP/WebSocket contracts,
assistant-envelope fields, trace/event payloads, or purely local presentation
labels.

## Implementation Gate

This document does not unblock real UI implementation.

Real UI implementation remains blocked until a separate approved task spec
defines:

- target surface
- approved communication contracts
- allowed and forbidden files
- ownership boundary
- mock-vs-real behavior
- tests and validation commands
- explicit non-ownership of backend/provider/runtime logic
