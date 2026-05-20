# Roadmap

Marvex is built as correct Assistant OS infrastructure first. The roadmap is a governance document, not permission to implement.

## Current Reality

Several surfaces that were once future-only now exist as bounded internal foundations. Contract approval still lives in `docs/CONTRACT_APPROVALS.md`.

Implemented and classified foundations include provider foundation, assistant envelope contracts, telemetry, Local API, Control Plane API and web, CapabilityRuntime, tool execution foundations, MCP adapter, SkillsRuntime, MemoryRuntime with SQLiteMemoryStore, MarketplaceRuntime, SessionRuntime, IntentRuntime, ContextRuntime, PromptHarnessRuntime, assistant loop primitives, and assistant turn integration.

The current cleanup phase is governance reconciliation, boundary hardening, and foundation cleanup before adding new capability surfaces.

## Phase 1: Provider Foundation

Provider-foundation contracts and explicit provider proof paths remain the current provider surface. Provider turns are still not the final assistant turn model.

## Phase 2: Bounded Internal Foundations

Bounded foundations may exist, be tested, and be safely refactored. They do not authorize product expansion, generic routing, arbitrary tool execution, raw payload persistence, service daemon behavior, UI expansion, voice, desktop, vision, or proactive behavior.

Every bounded foundation must have:

- an owning package or adapter boundary
- safe projection rules
- validation gates
- status and architecture documentation
- explicit scope limits

## Phase 3: Process Readiness

Future process work remains explicit and gated. Service placeholders stay README-only until matching service contracts are listed in `docs/CONTRACT_APPROVALS.md`. Local APIs must bind locally, require auth for protected endpoints, and remain HTTP/auth/JSON adapters only.

## Phase 4: Future Product Surfaces

Future product surfaces remain outside the current product surface until a matching contract is listed in `docs/CONTRACT_APPROVALS.md`:

- voice worker
- desktop agent
- shell/orb UI
- vision
- proactive behavior
- arbitrary browser/computer automation
- generic provider routing/model selection
- external marketplace install/execution

## Rule

Existing code is not approval. Future work is allowed only when supported by the current goal spec, docs/CONTRACT_APPROVALS.md, PROJECT_STATUS.md, validation gates, and relevant architecture docs.
