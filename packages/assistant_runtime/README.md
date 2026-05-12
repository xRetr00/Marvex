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
- expose an explicit experimental helper that converts accepted structured-output
  consumption into `AssistantTurnResult` using approved assistant-envelope
  contracts

Non-responsibilities:

- no provider-stage dispatcher
- no Core, CLI, ProviderRuntime, adapter, port, or service integration
- no provider bridge or provider calls
- no direct import of provider structured-output implementation details in the
  structured-output consumer seam
- no implicit or normal-turn structured-output conversion from
  `AssistantTurnRuntime.run(...)`
- no implicit structured-output use from normal `AssistantTurnRuntime.run(...)`
- no memory, tools, voice, UI, desktop, proactive, HTTP, IPC, daemon, or process
  runtime behavior
- no telemetry persistence, logging sink, or product trace storage

Structured-output consumer seam:

- `structured_output_consumer.py` is experimental and assistant-runtime-owned.
- `structured_output_runtime_entry.py` is an explicit experimental entry helper
  for this seam only.
- `structured_output_turn_result.py` is an explicit experimental result helper
  for converting the accepted local consumption draft into `AssistantTurnResult`.
- it accepts only sanitized handoff-like data through local draft models.
- it rejects unknown fields, unsafe metadata/payload keys, raw-preview payloads,
  prompt-like leakage, provider/session/thread identifiers, auth/token/secret
  markers, and direct validation/JSON exception detail.
- it preserves schema, trace, and turn identity while mapping known handoff
  statuses to assistant-runtime-owned consumption statuses.
- result conversion validates the parsed payload as `AssistantFinalResponse`,
  creates deterministic `structured_output_consumption` stage summaries, and
  maps non-usable handoff statuses to safe `ErrorEnvelope` results.
- optional trace emission goes through `packages.telemetry.sinks.make_trace_event(...)`
  so telemetry owns sanitization/redaction policy.
- compatibility with the provider-side handoff draft is proven only through
  JSON-compatible dict tests; neither package imports the other in production.
- the ProviderRuntime/provider_structured_output-to-AssistantRuntime bridge is
  proven only by `tests/integration` test helpers that call the existing
  ProviderRuntime experimental path, provider-side handoff draft builder, and
  `consume_structured_output_as_turn_result(...)`.
- these helpers are not exported from the package root and are not formal
  contracts, normal runtime orchestration, or product behavior.
