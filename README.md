# Marvex

<p align="center">
  <img src="assets/Marvex_WordMark_NoBackground.png" alt="Marvex logo" width="1920" />
</p>

Marvex is a service-ready modular desktop system. It starts as a Python Core
Service with a CLI client, provider adapters, and telemetry, then grows into a
process-ready desktop application where major modules can be replaced, disabled,
or moved into subprocesses.

`PROJECT_STATUS.md` is authoritative for the current phase and allowed work.
Implementation is allowed only through approved task slices with contracts,
tests, validation scripts, and final reports.

Agents should start orientation with `docs/SYSTEM_MAP.md`,
`docs/MODULE_INDEX.md`, and `docs/AGENT_CONTEXT_RULES.md` before broad source
discovery.

AI agents must run the validation scripts before finishing any task, including a
one-line hotfix. The required command is:

```powershell
uv run python scripts/run_all_checks.py
```

The user is not expected to review code correctness. Agents must not rely on
user code review as a safety mechanism. Every implementation step must be
controlled by contracts, task specs, tests, validation scripts, and a final
report.

## Current Implementation

Marvex has two approved implementation surfaces — provider foundation contracts and approved assistant envelope contracts — plus a set of bounded foundations classified in `docs/GOVERNANCE_CLASSIFICATION.md`. Bounded foundations include assistant turn integration, telemetry, local API, control plane API and web, capability runtime, tool execution foundations, MCP adapter, browser/computer-use adapter seam, memory runtime, memory tree and connectors, marketplace runtime, session runtime, intent/context/prompt harness runtimes, hybrid intent and web search, grounded evidence, adaptive context and learning, autonomy policy, and voice runtime.

Bounded foundations may be maintained and tested inside their current ownership boundaries but may not expand without an explicit goal update to `docs/CONTRACT_APPROVALS.md`, `PROJECT_STATUS.md`, validation gates, and architecture docs. Service placeholders under `services/` remain README-only until their service contracts are approved. See `docs/GOVERNANCE_CLASSIFICATION.md` for the full classification of each surface and its expansion state.

## Current Boundary

Allowed now:

- Documentation, templates, and validation scripts.
- README/status/library/schema governance cleanup.
- Approved task slices only.
- Service placeholder READMEs.

Forbidden now:

- Unapproved product behavior changes.
- Provider behavior changes outside approved adapter tasks.
- CLI behavior changes outside approved API tasks.
- Telemetry runtime behavior changes outside approved telemetry tasks.
- UI code.
- Tool execution.
- Memory systems.
- Voice, vision, desktop context, proactive behavior.

A roadmap entry, task id, or placeholder README is not permission to implement.

No turn endpoint exists yet as a generic, default, or product real-provider
execution surface. The only real-provider local API path is the explicit
developer-only LM Studio Responses runner.
No persistent trace storage, cross-process trace lookup, or trace streaming
exists yet.
No service daemon exists yet.
No subprocess runtime or service mode exists yet.
The local health/version API runner is manual smoke only, not product service behavior.
The local fake-turns API runner is also manual smoke only and fake-provider only.

Current AssistantRuntime CLI foundation modes are explicit and non-default:
`--assistant-runtime-fake-provider` for the deterministic fake path and
`--assistant-runtime-lmstudio-responses` for the LM Studio Responses proof path.
The real-provider proof remains opt-in only and does not approve service/API or
product behavior changes. Live LM Studio use is manual smoke only and is not
required by pytest or `scripts/run_all_checks.py`; the latest recorded manual
smoke for the proof path succeeded against a local LM Studio model.

## Capability Platform Foundation

Capability Platform Foundation adds `packages/capability_runtime` plus disabled/proof adapter seams under `packages/adapters/capabilities`. It establishes policy-governed capability proposals, context delivery, compaction, loop guards, fake deterministic dispatch proof, and safe lifecycle summaries without real tool execution.
