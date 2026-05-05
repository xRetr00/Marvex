# Provider Structured Output

Status: no-network adapter skeleton.

Responsibility: validate provider-like structured payload data into an approved
Marvex Pydantic contract.

Non-responsibilities:

- Provider execution.
- Prompt rendering.
- Runtime integration.
- Routing, retry, fallback, or schema registry behavior.
- Dependency or framework adoption.

The package accepts already-available structured data, validates it with a
caller-supplied Marvex contract model, and returns either the validated model or
an `ErrorEnvelope`.

`validate_structured_result(...)` is the narrow mapping helper for result-shaped
data. It extracts `structured_payload` and delegates validation to
`validate_structured_payload(...)`.
