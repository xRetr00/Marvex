# Marvex

<p align="center">
  <img src="assets/Marvex_WordMark_NoBackground.png" alt="Marvex logo" width="1920" />
</p>

Marvex is a service-ready modular desktop system. It starts as a Python Core
Service with a CLI client, provider adapters, and telemetry, then grows into a
process-ready desktop application where major modules can be replaced, disabled,
or moved into subprocesses.

`PROJECT_STATUS.md` is authoritative for the current phase and allowed work.
Implementation is allowed only through task slices with contracts,
tests, validation scripts, and final reports, and any contract-status question
must be answered in `docs/CONTRACT_APPROVALS.md`.

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

Marvex contains provider foundation contracts, assistant envelope contracts, and a set of bounded foundations classified in `docs/GOVERNANCE_CLASSIFICATION.md`. Those bounded foundations already exist in the repo and may be maintained or tested only inside their documented ownership and contract gates. Contract approval and contract status live only in `docs/CONTRACT_APPROVALS.md`.

Bounded foundations may be maintained and tested inside their current ownership boundaries. Any contract-status change must be recorded in `docs/CONTRACT_APPROVALS.md` first. Service placeholders under `services/` remain README-only until their matching contract is listed there. See `docs/GOVERNANCE_CLASSIFICATION.md` for the scope and ownership map of each surface.

## Current Boundary

Allowed now:

- Documentation, templates, and validation scripts.
- README/status/library/schema governance cleanup.
- Task slices tied to the documented surface map.
- Maintenance and tests within documented bounded foundations.
- Service placeholder READMEs.

Out of scope now:

- Product behavior for future surfaces that is not approved or implemented yet.
- Provider behavior changes outside the provider adapter boundary.
- CLI behavior changes outside the CLI boundary.
- Telemetry runtime behavior changes outside the telemetry boundary.
- UI code outside the Control Plane web boundary.
- Tool execution.
- Memory systems outside their bounded foundations.
- Voice, vision, desktop context, proactive behavior, shell/orb UI, and future service-daemon behavior.

A roadmap entry, task id, or placeholder README is not permission to implement.

The provider/CLI path remains the foundation/test path only.

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
