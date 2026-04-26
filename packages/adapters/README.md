# Adapters Package

Status: Provider Foundation adapters implemented.

Ownership: Concrete external integration boundary.

Responsibility: House concrete adapters that satisfy ports after contract
approval and library decisions. Current provider adapters include fake, LiteLLM,
and LM Studio Responses.

Forbidden responsibilities:

- Core orchestration.
- Business policy.
- Tool execution.
- Memory, intent, voice, UI, desktop context, or proactive behavior.
- Custom SDK code before library research.

Dependency direction:

- May depend on approved contracts and approved external SDKs inside adapter
  boundaries.
- Must not be imported by Core, ports, CLI, or telemetry.
