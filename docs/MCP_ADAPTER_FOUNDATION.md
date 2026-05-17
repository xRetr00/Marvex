# MCP Adapter Foundation

## Status

MCP Adapter Foundation is implemented as a safe, allowlisted, policy-gated adapter foundation. It uses the official MCP Python SDK for real MCP protocol mechanics, but it is not a product tool runtime, MCP host, registry installer, service daemon, or arbitrary server launcher.

## Ownership

`packages.adapters.capabilities.mcp` owns MCP protocol mechanics only: SDK session initialization, SDK tool listing, SDK tool-call invocation after CapabilityRuntime approval, and conversion from MCP SDK shapes into safe CapabilityRuntime-owned models.

CapabilityRuntime remains authoritative for manifests, capability refs, permission decisions, call proposals, execution requests, result envelopes, and safe projections. The MCP adapter cannot bypass CapabilityRuntime policy and cannot make a raw tool call path public.

## Implemented Surface

- `McpServerRef`, `McpToolRef`, transport metadata, and explicit allowlists.
- SDK-backed discovery through an injected official MCP SDK `ClientSession` boundary.
- Safe tool listing projections with dangerous tool-name blocking.
- Sanitized JSON-schema projection into `CapabilityManifest.input_schema` for allowed tools only.
- `McpToolCallProposal` creation only from allowed listings.
- SDK `call_tool(...)` only from an approved `CapabilityExecutionRequest`.
- `CapabilityResultEnvelope` summaries that expose result counts/types and status only.

## Safety Invariants

- No arbitrary MCP registry install.
- No hidden server launch or stdio process creation.
- No automatic tool calls.
- No shell, filesystem, browser, desktop, command, terminal, or network-named tools are enabled; they can appear only as blocked metadata.
- No raw tool input, output, prompt, transcript, credential, token, or provider payload persistence.
- No Core, AssistantRuntime, ProviderRuntime, RuntimeComposition, Local API, telemetry, MemoryRuntime, SessionRuntime, service, or CLI integration.

## Validation

The MCP boundary is covered by `scripts/check_mcp_adapter_boundaries.py` and included in `python scripts/run_all_checks.py`. Behavior tests live in `tests/capability_adapters/test_mcp_sdk_adapter.py` and use official SDK data models with a fake session boundary.
