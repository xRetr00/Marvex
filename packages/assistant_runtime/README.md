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

Non-responsibilities:

- no provider-stage dispatcher
- no Core, CLI, ProviderRuntime, adapter, port, or service integration
- no provider bridge or provider calls
- no memory, tools, voice, UI, desktop, proactive, HTTP, IPC, daemon, or process
  runtime behavior
- no telemetry persistence or output dispatch
