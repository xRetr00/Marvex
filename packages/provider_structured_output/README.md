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

`validate_fake_adapter_structured_result(...)` is a no-network skeleton helper
for fake adapter-shaped data. It extracts `trace_id` and
`result.structured_payload`, builds the current handoff shape, and delegates to
`validate_structured_result(...)`.

`validate_raw_structured_output(...)` is an adapter-local fallback validation
mapper. It accepts raw provider output text plus a caller-supplied Pydantic
model, validates only when the entire output is valid JSON, and returns
`StructuredOutputFallbackResult`.

The raw fallback mapper rejects empty output, malformed JSON, prose-wrapped
JSON, brace-scraped JSON, and Pydantic validation failures as
`invalid_structured_output`. It does not repair, scrape, retry, mutate prompts,
or integrate with runtime turn flow.

`StructuredOutputFallbackResult` metadata is hardened against hidden state and
raw provider leakage. Metadata must be JSON-compatible and may not contain
forbidden keys, including normalized variants such as `raw-output`,
`rawOutput`, `raw_provider_output`, prompt/session/conversation identifiers,
provider response identifiers, auth fields, tokens, secrets, or passwords.
Those checks apply recursively through nested objects and lists.

`sanitized_message` and `sanitized_error_code` are stable diagnostic fields, not
raw-error channels. They must not carry full JSON payloads, prompt-like text,
secret-bearing text, direct validation/JSON exception strings, or
secret-bearing error-code markers.

`raw_preview` is null by default. When explicitly enabled for diagnostics, it
is bounded to 300 characters and remains diagnostic-only; results carrying a
raw preview are not safe for default telemetry or logging. The package never
stores full raw provider output.

`map_adapter_raw_output_to_structured_result(...)` is an adapter-local usage
spike helper. It demonstrates how an adapter-shaped caller could pass raw output
text into `validate_raw_structured_output(...)`. The LM Studio Responses and
LiteLLM adapters have adapter-local hooks for this helper, but those hooks are
not wired to normal ProviderRuntime turns, Core, AssistantTurnRuntime handoff,
CLI behavior, service/API/WebSocket behavior, or runtime turn flow.

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

## ProviderRuntime And Handoff Boundary

This package currently owns validation and mapping helpers only.
`StructuredOutputFallbackResult` is not a Core contract, port contract,
AssistantTurnRuntime handoff, telemetry format, or user-facing response
contract.

Task 094 implemented an explicit ProviderRuntime experimental call path. That
path may select LM Studio Responses or LiteLLM through the existing provider
factory and call the adapter-local `map_raw_output_to_structured_result(...)`
hook. Task 095 hardened the path with boundary and leak regressions.

The ProviderRuntime path remains experimental:

- it does not change normal provider `send()` behavior.
- it does not change `ProviderResponse`.
- it does not parse JSON, repair JSON, scrape braces, parse markdown fences,
  mutate prompts, retry structured-output failures, construct fallback results,
  convert results to `ProviderResponse` or `AssistantTurnResult`, emit
  user-facing responses, or log raw provider output.

Task 096 decides the handoff boundary:

- `StructuredOutputFallbackResult` may cross the ProviderRuntime boundary only
  as the return value of the explicit experimental ProviderRuntime path.
- it may not enter AssistantRuntime directly in normal assistant turns.
- it may not enter Core directly.
- it is not promoted to a formal contract now.
- it may not be converted to `AssistantTurnResult` now.

Future AssistantRuntime/Core handoff work remains blocked until a separate
explicit task names the exact caller, callee, input shape, output shape, failure
mapping, trace behavior, and tests. Core, AssistantTurnRuntime normal-turn
behavior, CLI normal-turn behavior, service/API/WebSocket behavior,
port/contract changes, telemetry storage, product runtime behavior, and formal
handoff contract promotion remain blocked.
