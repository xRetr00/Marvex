# Agent Execution Loop and Tool-Orchestrated Turn Foundation

Status: complete foundation boundary.

This foundation models a bounded assistant turn that can include eligible capabilities, provider tool-call proposals, permission decisions, human approval pauses, approved safe execution requests, safe result envelopes, provider continuation readiness, and final response readiness.

CapabilityRuntime remains authoritative for permission, approval, dispatch eligibility, execution-request validation, result envelopes, loop guards, and safe telemetry summaries. AssistantRuntime may coordinate lifecycle-ready summaries through `packages.assistant_runtime.tool_orchestration`, but it does not import adapters or execute tools.

## Ownership

- CapabilityRuntime owns `AgentLoopState`, `AgentLoopStep`, `AgentLoopDecision`, `AgentLoopStopReason`, `AgentLoopGuardResult`, `ToolOrchestrationState`, `PendingApprovalState`, `ToolContinuationState`, `SafeAgentLoopProjection`, approval decisions, execution requests, denial envelopes, loop guards, and telemetry-safe counts.
- AssistantRuntime owns only the `ToolOrchestratedTurnState` lifecycle coordination helper and safe lifecycle summary linkage.
- Tool adapters execute only approved `CapabilityExecutionRequest` paths for this foundation proof. The safe built-in catalog can execute the calculator through an approved request and returns a `CapabilityResultEnvelope` with raw input/output persistence disabled.
- ProviderRuntime still owns provider construction only. Provider tool calls are proposals; they are never execution permission by themselves.
- Telemetry may receive counts and stop reasons only; it must not own loop state or persist raw tool/browser/computer/provider payloads by default.

## Approval And Loop Safety

Risky actions can pause for human approval through `PendingApprovalState` and `AgentLoopGuardResult.human_approval_pause(...)`. Denial returns a safe denial result envelope. Approved execution requires an approved permission decision and, for risky proposals, an approved human `ApprovalDecision` before `CapabilityExecutionRequest` validation succeeds.

Loop safety is bounded by max steps, repeated-failure guard state, explicit stop reasons, and proposal-only/dry-run/approval-ready execution modes inherited from the tooling foundation.

## Safe Continuation

Tool results are represented for provider continuation through `ToolContinuationState`. The continuation state exposes result status and readiness only, not raw tool output. AssistantRuntime lifecycle summaries expose `agent_loop_step_count` and `tool_result_delivery_ready` only.

## Blocked

Blocked: autonomous agents, shell/terminal execution, filesystem write/edit/delete tools, arbitrary browser/computer actions, credential entry/extraction, purchase/payment/checkout, CAPTCHA or anti-bot bypass, UI, voice, desktop control, vision, proactive behavior, generic provider routing, and raw prompt/transcript/tool/provider payload persistence by default.