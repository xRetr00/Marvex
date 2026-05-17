# Library Decision: Official MCP Python SDK

library name: MCP Python SDK

official source: https://github.com/modelcontextprotocol/python-sdk and https://modelcontextprotocol.io/

maintenance status: Active as of April 29, 2026. PyPI latest version observed as `mcp==1.27.0`. The GitHub repository identifies itself as the official Python SDK for Model Context Protocol servers and clients and links to the protocol documentation and specification.

why use it: Marvex should not hand-roll MCP JSON-RPC, transport handling, tool discovery, or tool-call envelopes. The official SDK is the correct component if Marvex later exposes or consumes MCP servers.

why not custom code: Custom MCP code would duplicate a moving protocol, increase interoperability risk, and likely miss transport/security edge cases. MCP should be a component-level adapter dependency, not a Marvex-built protocol implementation.

fallback if abandoned: Keep MCP behind a worker/adapter boundary so Marvex can replace the SDK, disable MCP, or support only explicit native tools through a separate task.

pyproject dependency: none in Task 033

declared dependency: not declared; Task 033 must not edit pyproject.toml

verified date: 2026-04-29

verified by: Codex

scope: Candidate only. Future use must be limited to MCP client/server adapters. It must not introduce a tool runtime, agent runtime, broad tool exposure, or direct Core dependency.

architecture fit: Good for future MCP integration after policy gates and tool boundaries exist. It belongs behind Tool Worker or MCP adapter boundaries, not inside Core.

adopt / defer / reject decision: Defer for implementation, adopt as the preferred official SDK when MCP work is approved. Task 033 does not build MCP runtime.

risks: MCP tool execution can cross trust boundaries. STDIO/server launch paths are high risk and require allowlists, sandboxing, explicit config, and policy checks. Tool discovery must not mean tool exposure.

comparison to custom routing: MCP is not an intent router. It must not influence route selection except through explicit tool capability metadata consumed after policy approval.

## Capability Platform Update - 2026-05-17

Decision: create adapter seam now, backend disabled until later.

The Capability Platform Foundation introduces `packages/adapters/capabilities/mcp.py` with MCP server refs, tool refs, allowlists, transport values (`stdio`, `sse`, `streamable_http`), listing projections, call proposals, and a disabled backend. The official MCP Python SDK remains the required dependency when Marvex introduces real MCP protocol mechanics. It is not added in this phase because the implementation intentionally forbids arbitrary server execution, registry installs, auto-call behavior, and real MCP tool execution.

This preserves the library-first rule without hand-rolling MCP protocol code: Marvex models the adapter boundary now, and the SDK adoption point remains a later explicit task.
