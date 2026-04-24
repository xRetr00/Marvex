# Provider Adapters Package

Status: skeleton only.

Ownership: Provider adapter placement boundary.

Responsibility: Future concrete adapters that satisfy provider ports.

Forbidden responsibilities:

- Core orchestration.
- Business policy.
- Tool execution.
- Memory, intent, voice, UI, desktop context, or proactive behavior.
- Provider behavior before an approved adapter task.

Dependency direction:

- May depend on ports and approved contracts.
- Must not be imported by Core, ports, CLI, or telemetry.

