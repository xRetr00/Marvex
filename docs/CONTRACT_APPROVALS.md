# Contract Approvals

This registry controls whether a documented contract may be used for implementation. It is the only file in the repository that records approval state. Contract approval and contract status live only in `docs/CONTRACT_APPROVALS.md`.

`docs/CONTRACTS.md` describes intended contract shapes. A contract is not implementation-approved until this registry says `approval_status: approved` and `implementation_allowed: yes`.

The current approved contracts include provider-foundation contracts and the
smallest assistant envelope contracts. Provider-foundation contracts are still
not full assistant-turn contracts.

The approved assistant-envelope contracts may be used by future implementation
tasks, but approval does not implement Pydantic models, runtime behavior, Core
behavior, CLI behavior, ProviderRuntime behavior, tools, memory, voice, UI,
desktop, proactive behavior, HTTP, IPC, or service runtime.

## Approval Fields

- `contract_name`: Stable contract or service contract name.
- `schema_version`: Contract schema version.
- `approval_status`: `draft`, `approved`, `deprecated`, or `blocked`.
- `approver`: Human or review authority that approved the contract. Use `none` while draft.
- `approval_date`: ISO date, or `none` while draft.
- `implementation_allowed`: `yes` or `no`.

## Current Registry

| contract_name | schema_version | approval_status | approver | approval_date | implementation_allowed |
| --- | --- | --- | --- | --- | --- |
| TurnInput | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| TurnOutput | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| FinalResponse | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| ProviderRequest | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| ProviderResponse | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| TraceEvent | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| ErrorEnvelope | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| HealthCheck | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| VersionInfo | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| InputEvent | 0.1.1-draft | approved | user | 2026-05-01 | yes |
| AssistantTurnInput | 0.1.1-draft | approved | user | 2026-05-01 | yes |
| AssistantTurnResult | 0.1.1-draft | approved | user | 2026-05-01 | yes |
| AssistantFinalResponse | 0.1.1-draft | approved | user | 2026-05-01 | yes |
| CoreService | 0.1.1-draft | approved | user | 2026-05-19 | yes |
| ProviderWorker | 0.1.1-draft | approved | user | 2026-05-19 | yes |
| ToolWorker | 0.1.1-draft | approved | user | 2026-05-19 | yes |
| IntentWorker | 0.1.1-draft | approved | user | 2026-05-19 | yes |
| VoiceWorker | 0.1.1-draft | approved | user | 2026-05-19 | yes |
| DesktopAgent | 0.1.1-draft | approved | user | 2026-05-22 | yes |
| Proactive | 0.1.1-draft | approved | user | 2026-05-22 | yes |
| Shell | 0.1.1-draft | approved | user | 2026-05-22 | yes |
| MemoryService | 0.1.1-draft | draft | none | none | no |
| TelemetryEventService | 0.1.1-draft | draft | none | none | no |
| PolicyPermissionService | 0.1.1-draft | draft | none | none | no |

## Approval Rules

- Approval changes require an updated task spec and final report.
- `schema_version` must change when compatibility is broken.
- `approval_status: approved` is invalid without an approver and approval date.
- `implementation_allowed: yes` is invalid unless approval status is `approved`.
- Service placeholder folders remain README-only until their matching service contract has `implementation_allowed: yes`.
- CoreService approval is limited to the pure `packages/core/service.py`
  orchestration foundation and the minimal local `services/core/main.py`
  service entrypoint. It does not approve remote binding, daemon supervision,
  provider-specific service branches, raw prompt/provider-output persistence,
  hidden autostart, memory/tools/desktop/UI/vision/proactive behavior, or other
  service implementations.

## Implementation Surface Classification Rule

Existing code is not approval. Future work is allowed only when supported by the current goal spec, `docs/CONTRACT_APPROVALS.md`, `PROJECT_STATUS.md`, validation gates, and relevant architecture docs.

`docs/GOVERNANCE_CLASSIFICATION.md` is the current registry for implemented and future surfaces. The registry distinguishes approved implementation surfaces, bounded foundations, experimental seams, future service contracts, and forbidden product behavior for now.

Existing bounded foundations may be maintained, tested, and safely refactored inside their current boundaries. They must not expand into product behavior unless this approval registry, project status, validation gates, and architecture docs are updated by an explicit future goal.

## Current Surface Summary

- provider foundation: approved implementation surface for provider-foundation scope only.
- assistant turn contracts: approved implementation surface only for approved assistant envelope contracts.
- assistant turn integration: bounded foundation; expansion blocked without explicit approval.
- telemetry: bounded foundation; safe summaries/persistence only.
- local api: bounded foundation; HTTP/auth/JSON only.
- control plane api: bounded foundation; safe projections and approval APIs only.
- control plane web: bounded foundation; isolated local admin dashboard only.
- capability runtime: bounded foundation; policy/approval/dispatch/result envelopes only.
- tool execution foundations: bounded foundation; approved safe requests only.
- mcp adapter/seam: bounded foundation; official SDK and allowlist only.
- browser/computer-use adapter/seam: experimental seam; product automation blocked.
- memory runtime: bounded foundation; safe refs/backend only.
- memory service: future service contract; README-only.
- marketplace runtime: bounded foundation; read-only metadata/proposals only.
- session runtime: bounded foundation; safe refs only.
- intent/prompt harness seams: bounded foundation; safe projections and bounded prompt plans only.
- intent worker process: approved local JSONL classification boundary; no providers, no approvals, no execution.
- tool worker process: approved local JSONL CapabilityRuntime execution boundary; policy/approval enforced before safe execution.
- service placeholders: future service contract; README-only except approved local CoreService, ProviderWorker, IntentWorker, and ToolWorker entrypoint files.
- telemetry event service: future service contract; README-only.
- policy permission service: future service contract; README-only.
- voice runtime foundation: bounded implementation foundation for in-process voice I/O orchestration only; no separate service process, visual shell, hidden recording, or raw audio/transcript persistence by default.
- voice worker runtime: approved implementation surface for local-only VoiceWorker process, lifecycle, safe worker commands/events, microphone/playback adapters, model asset readiness, and protected Control Plane projections; no hidden recording, remote exposure, raw audio/transcript persistence, Orb/shell UI, desktop agent, vision, or proactive behavior.
- shell: approved product surface for the local Windows tray supervisor, chat/control UI host, status pill/waveform overlay, Spotlight/approval surface, autostart, single-instance, and installer. It is a loopback client only and must not implement provider, intent, tool, voice, cognition, memory, policy, desktop-agent, vision, or proactive logic.
- desktop agent: approved local-only perception worker surface for focused-window content via Windows UI Automation adapters and screenpipe recall through the existing MCP adapter path. It returns safe bounded projections only and must not persist raw screen frames, audio, keystrokes, transcripts, payloads, or secrets.
- proactive behavior: approved bounded initiative-proposal runtime surface. It watches safe DesktopAgent projections and Assistant STATE, applies user-mutable learning preferences, remains explicit/visible/local-only, and must not execute hidden background actions.
- future vision: future service contract or forbidden product behavior for now unless a later goal explicitly approves it.
