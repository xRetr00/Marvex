# Core Rules

The Core Service owns turn orchestration. It does not own every decision in the product.

## Hard Rules

- Core cannot import UI.
- Core cannot import LM Studio directly.
- Core cannot import tools directly.
- Core cannot own provider-specific logic.
- Core cannot treat the provider turn as the assistant turn.
- Core only talks to ports and interfaces.
- Ports are contracts only, never registries, routers, runtimes, or implementation containers.
- `ProviderPort` must remain a minimal method contract and must not mention concrete providers.
- Tool ports must remain minimal contracts only, including `ToolExecutorPort: execute(ToolCall) -> ToolResult`.
- Core cannot import adapters.
- Adapters cannot import Core.
- Selection, dispatch, retry, and lifecycle logic live in runtime layers, not in ports.
- Core must not use hidden global state.
- No god files.
- No file over 500 lines without explicit justification.
- No port contract file over 120 lines without explicit justification.
- No registry or factory file over 250 lines without split or explicit justification.
- No feature before contract.
- No provider-specific branches in the orchestrator.

## Refactor Safety

Core changes require:

- task spec
- contract diff if contracts change
- fake adapter tests
- replay tests when behavior changes
- migration plan
- rollback plan

## Ownership

Core owns:

- turn lifecycle
- provider port call
- final response normalization
- trace lifecycle emission

These are provider-foundation responsibilities. Assistant-level lifecycle work
requires an approved Assistant Turn Spine and approved assistant contracts before
implementation.

For future assistant runtime work, Core owns the assistant lifecycle envelope.
AssistantTurnRuntime owns assistant stage dispatch. Core must not own assistant
stage internals.

Core does not own:

- provider protocol details
- memory
- tools
- UI
- voice
- desktop context
- proactive behavior
- intent classification

## Current Foundation Ownership Guard

Existing code is not approval. Core remains orchestration-only even when bounded foundations exist elsewhere. Future work is allowed only when supported by the current goal spec, `docs/CONTRACT_APPROVALS.md`, `PROJECT_STATUS.md`, validation gates, and relevant architecture docs.

Core must not absorb CapabilityRuntime policy, assistant turn integration stage logic, memory policy, marketplace metadata, Control Plane behavior, browser/computer-use adapter behavior, MCP mechanics, skills logic, voice, desktop, shell/orb UI, proactive behavior, or vision.
