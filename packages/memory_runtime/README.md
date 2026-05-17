# MemoryRuntime

`packages.memory_runtime` owns the narrow Memory Foundation. It defines safe
memory records, memory references, write candidates, read results, forget
results, safe projections, and an optional current-process-only store.

## Owned Surface

- `MemoryRef` and safe memory ids
- `MemoryRecord` for policy-authorized memory content
- `MemoryWriteCandidate` for pending future write review
- `MemoryReadResult` and `MemoryForgetResult` safe projections
- `CurrentProcessMemoryStore` for explicit current-process proof only

## Boundary Rules

- Memory means policy-governed assistant recall material such as safe facts,
  preferences, instructions, or summaries.
- Memory is not a transcript store, prompt store, provider payload store,
  telemetry store, session store, or tool/UI/voice/desktop/vision/proactive
  state store.
- Memory records may link to `session_ref`, `conversation_ref`, `trace_id`, and
  `turn_id` only as references.
- `previous_response_id` is provider continuity input, not memory.
- Raw transcripts, raw prompts, provider payloads, provider outputs, tokens,
  credentials, environment values, and secrets must not be stored by default.

## Current Store

`CurrentProcessMemoryStore` is instance-owned and disappears with the process.
It exists to prove the boundary and read/forget shapes; it is not long-term
recall, file persistence, embeddings, vector search, or product memory.

