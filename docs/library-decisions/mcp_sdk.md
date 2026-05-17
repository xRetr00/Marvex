# Library Decision: Official MCP Python SDK

library name: mcp

official source: https://github.com/modelcontextprotocol/python-sdk and https://modelcontextprotocol.io/

maintenance status: Active as of May 18, 2026. PyPI latest version observed locally with `python -m pip index versions mcp` as `mcp==1.27.1`.

why use it: Marvex must not hand-roll MCP protocol clients, JSON-RPC envelopes, transport session behavior, tool listing, or tool call protocol mechanics. The official MCP Python SDK is the approved dependency for MCP client/session mechanics inside the MCP adapter boundary.

why not custom code: Custom MCP protocol code would duplicate a moving protocol, increase interoperability risk, and likely miss session, initialization, transport, and result-shape edge cases that the official SDK already owns.

fallback if abandoned: Keep MCP behind `packages.adapters.capabilities.mcp` and the future Tool Worker boundary so Marvex can replace the SDK, disable MCP, or support only explicit native tools without changing Core or CapabilityRuntime policy ownership.

pyproject dependency: mcp

declared dependency: mcp==1.27.1

verified date: 2026-05-18

verified by: Codex

scope: Adopted for the MCP Adapter Foundation only. `packages.adapters.capabilities.mcp` may use the official SDK `ClientSession`, `Tool`, and `CallToolResult` shapes for approved sessions. The adapter must not launch arbitrary MCP servers, install registry entries, auto-call tools, persist raw payloads, or bypass CapabilityRuntime permission and execution envelopes.

architecture fit: Good. MCP protocol mechanics belong behind the adapter/worker boundary; CapabilityRuntime remains authoritative for capability refs, manifests, permission decisions, call proposals, execution requests, and safe result envelopes. Core, AssistantRuntime, ProviderRuntime, Local API, RuntimeComposition, MemoryRuntime, SessionRuntime, and telemetry must not become MCP protocol owners.

adopt / defer / reject decision: Adopt narrowly for MCP protocol mechanics in the MCP adapter. Defer transport/server-launch ownership, registry install, broad tool execution, and product runtime integration to future explicit tasks.

risks: MCP tool discovery can expose dangerous local or remote capabilities. STDIO/server launch paths are high risk. Tool schemas and tool results may contain sensitive data. Mitigations in this phase: explicit server/tool allowlists, dangerous tool-name blocking, schema sanitization, CapabilityRuntime proposal/execution request requirements, safe result summaries only, and no raw input/output persistence.

comparison to custom routing: MCP is not an intent router or assistant brain. It supplies protocol mechanics for tool discovery/calls after Marvex policy approval; it must not influence route selection except through explicit safe capability metadata consumed by CapabilityRuntime.

## MCP Adapter Foundation - 2026-05-18

Decision: adopt the official MCP Python SDK for real MCP protocol mechanics while keeping the adapter policy-gated and non-launching.

The MCP Adapter Foundation updates `packages/adapters/capabilities/mcp.py` from a disabled proof seam to an SDK-backed adapter boundary. It accepts an already-approved SDK `ClientSession`, initializes and lists tools only for allowlisted server refs, converts allowed tools into safe `CapabilityManifest` projections, creates `CapabilityCallProposal` objects, and calls tools only from approved `CapabilityExecutionRequest` envelopes. It returns `CapabilityResultEnvelope` summaries without raw output content.

This does not add arbitrary MCP registry install, stdio server launching, hidden transport creation, automatic tool calls, shell/filesystem/browser/desktop/network tool enablement, Core integration, Local API integration, ProviderRuntime integration, AssistantRuntime integration, or runtime turn-flow integration.
