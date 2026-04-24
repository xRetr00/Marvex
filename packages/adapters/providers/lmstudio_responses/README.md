# LM Studio Responses Adapter Package

Status: skeleton only.

Ownership: Future LM Studio Responses-compatible provider adapter.

Responsibility: Future placement for adapter code after library verification and contract approval.

Forbidden responsibilities:

- HTTP calls before the adapter task is approved.
- Provider payload construction before the adapter task is approved.
- Fake provider behavior.
- Core orchestration.
- Model routing or fallback policy.

Dependency direction:

- May depend on provider ports and approved contracts when implementation is approved.
- Must not be imported by Core, ports, CLI, or telemetry.

