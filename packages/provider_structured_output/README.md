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

Expected handoff shape:

```json
{
  "trace_id": "trace-handoff-001",
  "structured_payload": {
    "schema_version": "0.1.1-draft",
    "response_type": "text",
    "text": "Done.",
    "payload_ref": null,
    "output_channel_intent": "default",
    "safe_for_display": true,
    "safe_for_speech": true,
    "memory_write_candidate_hint": false,
    "finish_reason": "stop",
    "metadata": {}
  }
}
```

The handoff object is intentionally minimal. It carries trace context and
already-structured payload data only; response identifiers and runtime
references are outside this package.
