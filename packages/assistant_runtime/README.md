# Assistant Runtime Foundation

This package contains pure helpers for constructing approved assistant-envelope
contracts.

Current responsibilities:

- normalize simple text input into `InputEvent`
- create `AssistantTurnInput` from an existing input event
- assemble text `AssistantFinalResponse` objects
- assemble no-provider success or hard-failure `AssistantTurnResult` objects
- build deterministic reference-only stage summaries for the no-provider path
- run a minimal deterministic `AssistantTurnRuntime` skeleton over an existing
  `AssistantTurnInput`
- validate an isolated experimental structured-output handoff-like input draft
  for future-stage consumption only, without creating final responses
- expose an explicit experimental helper for future-stage structured-output
  consumption from a local draft model or a sanitized plain dict

Non-responsibilities:

- no provider-stage dispatcher
- no Core, CLI, ProviderRuntime, adapter, port, or service integration
- no provider bridge or provider calls
- no direct import of provider structured-output implementation details in the
  structured-output consumer seam
- no structured-output conversion to `AssistantTurnResult` or user-facing final
  response
- no implicit structured-output use from normal `AssistantTurnRuntime.run(...)`
- no memory, tools, voice, UI, desktop, proactive, HTTP, IPC, daemon, or process
  runtime behavior
- no telemetry persistence or output dispatch

Structured-output consumer seam:

- `structured_output_consumer.py` is experimental and assistant-runtime-owned.
- `structured_output_runtime_entry.py` is an explicit experimental entry helper
  for this seam only.
- it accepts only sanitized handoff-like data through local draft models.
- it rejects unknown fields, unsafe metadata/payload keys, raw-preview payloads,
  prompt-like leakage, provider/session/thread identifiers, auth/token/secret
  markers, and direct validation/JSON exception detail.
- it preserves schema, trace, and turn identity while mapping known handoff
  statuses to assistant-runtime-owned consumption statuses.
- compatibility with the provider-side handoff draft is proven only through
  JSON-compatible dict tests; neither package imports the other in production.
- it is not exported from the package root and is not a formal contract.
