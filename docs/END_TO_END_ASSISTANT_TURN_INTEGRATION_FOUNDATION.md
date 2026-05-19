# End-to-End Assistant Turn Integration Foundation

Status: complete bounded integration foundation with assistant-intelligence checkpoint.

This foundation adds a bounded assistant-turn spine in `packages.assistant_turn_integration`. It integrates the approved runtime layers without turning Local API, RuntimeComposition, Core, ProviderRuntime, Telemetry, Control Plane, or any adapter into the assistant brain.

## Turn Spine

The integration proof accepts an `AssistantTurnInput` through an injected Local API turn handler, links safe session/conversation refs, classifies intent through IntentRuntime or an injected semantic-router-backed IntentRuntime adapter result, selects safe context through ContextRuntime, assembles a bounded prompt plan through PromptHarnessRuntime, runs a fake provider stage through AssistantRuntime provider-stage machinery, handles a CapabilityRuntime tool proposal, executes the safe built-in calculator only through an approved `CapabilityExecutionRequest`, records a safe result envelope, and returns provider continuation/final response readiness. Memory Tree evidence refs can participate as bounded source/topic/daily evidence counts and identifiers only; raw memory content and quote previews are not injected into prompts or telemetry.

CapabilityRuntime owns policy/approval/dispatch, execution request validation, result envelopes, and loop guard models. IntentRuntime owns intent/route decisions. ContextRuntime owns context selection. PromptHarnessRuntime owns prompt plan construction. AssistantRuntime owns lifecycle coordination. Telemetry owns trace persistence and safe trace reads. Local API owns HTTP/auth/JSON only. Control Plane displays safe trace, approval, and runtime summaries only.

## Approval and Control Plane Visibility

Risky browser/computer intent becomes a pending approval request and does not execute. The existing Control Plane approval store can list/read/deny/approve the request through safe projections. The integration store can project trace summaries, pending approvals, safe tool/capability summaries, session refs, agent-loop summaries, telemetry counts, and settings into `ControlPlaneSnapshot` without raw payloads.

## Safety

The spine does not implement voice, Orb, desktop overlay, proactive behavior, arbitrary browser/computer actions, shell execution, filesystem write/edit/delete, MCP execution, generic provider routing, or model selection. Raw prompts, transcripts, provider payloads, tool payloads, browser DOM, screenshots, tokens, secrets, and environment values are not persisted by default.

Validation is enforced by `scripts/check_end_to_end_turn_boundaries.py` and end-to-end tests under `tests/assistant_turn_integration`.
