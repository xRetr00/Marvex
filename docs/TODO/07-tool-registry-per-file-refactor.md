# 07 — Tool registry: per-file tool refactor

**Theme:** Reasoning / Infra · **Size:** L · **Status:** not started · **Enabler for 02**

## Problem

Built-in tools are defined and dispatched in the wrong shape for real
tool-use. They live in two large files with hand-written `if/elif` dispatch
ladders keyed on string identifiers, there is no single place that describes a
tool's **model-facing schema**, and adding a tool means editing several
ladders. This is why:

- The model hallucinates capabilities it doesn't have ("I'll route this to the
  agent.deep_search subagent / your RAG tools") — there is no authoritative,
  model-visible list of real tools to ground it.
- Item 02 (agentic tool-calling) can't generate tool schemas cleanly because
  each tool's input contract is scattered across pydantic request models,
  regex slot parsers, and dispatch branches.

The user's ask: **one Python file per tool** (`read.py`, `list.py`,
`search.py`, `write.py`, `patch.py`, `calculator.py`, …), each a
self-contained unit with name, description, JSON schema, risk/side-effect
metadata, and an `execute()` — collected by a single registry.

## Evidence (current state)

- `packages/adapters/capabilities/builtins.py` (284 lines): `CalculatorBuiltin`,
  `TimeDateBuiltin`, `CapabilityDiagnosticsBuiltin`, `RepoStatusBuiltin` all in
  one file; `BuiltinToolCatalog.execute_request` dispatches with a
  `if request.proposal.capability_ref.identifier == "builtin.calculator": … elif
  "builtin.time_date": … elif …` ladder.
- `packages/adapters/capabilities/files.py` (264 lines):
  `ReadOnlyFileExecutor.execute` dispatches `file.read / file.list / file.search
  / file.rg` via another `if/elif` ladder; `SandboxedFileWriteExecutor` is a
  separate class for `file.write`. No `patch`/append tool exists yet.
- Slot/argument parsing for these tools lives **outside** the tool, as regex in
  `services/core/main.py` + `packages/core/orchestration/file_intent.py`
  (`file_request_from_input`, `file_write_request_from_input`). So a tool's
  "input schema" is implicit and duplicated.
- `to_manifest()` emits a `CapabilityManifest` with `input_schema={"type":
  "object"}` — i.e. no real schema. Tool-use (item 02) needs the real per-tool
  parameter schema here.

## Target structure

```
packages/adapters/capabilities/tools/
  __init__.py            # registry: discover + lookup + manifests + schemas
  base.py                # Tool protocol/ABC: id, name, description, risk,
                         #   side_effect, params_model (pydantic), execute()
  calculator.py          # CalculatorTool
  time_date.py           # TimeDateTool
  read.py                # ReadFileTool        (file.read)
  list.py                # ListDirectoryTool   (file.list)
  search.py              # SearchFilesTool     (file.search)
  ripgrep.py             # RipgrepTool         (file.rg)
  write.py               # WriteFileTool       (file.write)
  patch.py               # PatchFileTool       (file.patch  - NEW: append/edit)
  diagnostics.py         # CapabilityDiagnosticsTool
  repo_status.py         # RepoStatusTool
```

Each tool module exposes a class implementing a uniform `Tool` interface:

```python
class Tool(Protocol):
    id: str                       # "file.read"
    name: str                     # "Read file"
    description: str              # model-facing, one sentence
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel
    params_model: type[BaseModel] # pydantic -> JSON schema for tool-use
    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope: ...
    def json_schema(self) -> dict  # derived from params_model
    def to_manifest(self) -> CapabilityManifest
```

The registry replaces both `if/elif` ladders with a `dict[id -> Tool]` lookup,
and provides:
- `registry.execute(request)` — dispatch by `capability_ref.identifier`.
- `registry.manifests()` — for the capability platform.
- `registry.tool_schemas()` — JSON tool schemas for item 02's agent loop.

## Proposed approach (staged, non-breaking)

1. **Add `tools/base.py` + registry** alongside the existing files; do not
   delete anything yet.
2. **Port one tool at a time** into its own module, registering it. Start with
   calculator (simplest), then the file tools.
3. **Shim the old API:** `BuiltinToolCatalog.execute_request` and
   `ReadOnlyFileExecutor.execute` delegate to `registry.execute(...)` so every
   existing caller (`services/core/main.py`, the assistant_turn_integration
   stages, tests) keeps working unchanged.
4. **Move arg schemas into the tools:** each tool owns its `params_model`. The
   regex slot parsers in `file_intent.py` become *fallback* producers of those
   params (and, after item 03, the LLM produces them) — the tool validates.
5. **Add the missing `patch` tool** (append / replace-in-file) since the user
   listed it and write-only is limiting.
6. **Delete the ladders** once all callers go through the registry and tests are
   green.

## New small bug to fix in passing

`file.write` raises `file.exists` whenever the target exists and
`overwrite=False`, and `file_write_request_from_input` always sets
`overwrite: False`. Result: "create a file" on an existing name hard-fails
(seen in the field as "File write did not complete: file.exists"). The
`write.py`/`patch.py` split should define clear semantics:
- `write` with explicit "overwrite/replace" intent → `overwrite=True`.
- `write` to an existing file without that intent → either auto-suffix
  (`name (1).md`) or route to `patch` (append). Decide and document.

## Affected files (anticipated)

- New `packages/adapters/capabilities/tools/` package.
- `packages/adapters/capabilities/builtins.py`, `files.py` — become thin shims,
  then removed.
- `services/core/main.py` — dispatch + arg-building through the registry.
- `packages/assistant_turn_integration/stages/tools.py` — uses the registry.
- Boundary/`__init__` exports + tests.

## Acceptance criteria

- Every built-in tool lives in its own file under `tools/` with a uniform
  interface; no `if/elif` dispatch ladders remain.
- `registry.tool_schemas()` returns valid JSON schemas usable by item 02.
- All existing tool tests pass against the registry-backed shims.
- A `patch`/append tool exists; "create a file that already exists" no longer
  hard-fails (defined overwrite/append/suffix behavior).

## Risks / notes

- This is the **enabler for item 02** — do it first within the agent-tooling
  workstream. Clean per-tool schemas make model tool-calling tractable.
- Keep the process/approval boundary intact: tools still execute behind the
  ToolWorker and risky ones still require approval.
