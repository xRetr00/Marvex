import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const snapshot = {
  schema_version: "1",
  providers: [{ provider_id: "lmstudio_responses", configured: true, secret_present: true, secret_value_present: false }],
  capabilities: [{ identifier: "builtin.calculator", kind: "tool", risk_level: "safe" }],
  tools: [{ tool_id: "builtin.calculator", side_effect_level: "read_only" }],
  mcp_servers: [{ server_id: "local-test-mcp", allowlisted: true, tool_count: 1 }],
  skills: [{ skill_id: "test.fake_skill", validated: true }],
  traces: [{ trace_id: "trace-1", event_count: 2, raw_payload_persisted: false }],
  memory: [{ memory_ref: "memory:1", record_count: 1 }],
  sessions: [{ session_id: "session-1", conversation_count: 1 }],
  agent_loops: [{ loop_id: "loop-1", step_count: 1, stop_reason: "waiting_for_human_approval" }],
  telemetry: { trace_count: 1, raw_payload_persisted: false },
  settings: { browser_tools_enabled: false, computer_use_enabled: false },
  raw_payload_persisted: false,
  approvals: {
    schema_version: "1",
    pending_count: 1,
    raw_payload_persisted: false,
    approvals: [{
      schema_version: "1",
      approval_request_id: "approval-request-1",
      trace_id: "trace-1",
      turn_id: "turn-1",
      capability_summary: { kind: "tool", identifier: "browser.click" },
      user_visible_summary: "Allow browser click on the active page?",
      risk_level: "high",
      side_effect_level: "browser_action",
      execution_mode: "requires_approval",
      status: "pending",
      raw_payload_persisted: false
    }]
  }
};

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><App /></QueryClientProvider>);
}

describe("Control Plane app", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders dashboard and approval risk labels from safe API data", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(snapshot), { status: 200, headers: { "Content-Type": "application/json" } })));

    renderApp();

    expect(await screen.findByText("Marvex Control Plane")).toBeInTheDocument();
    expect(await screen.findByText("Pending approvals")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Approvals/i }));
    expect(await screen.findByText("browser.click")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.queryByText(/secret-value/i)).not.toBeInTheDocument();
  });

  it("renders marketplace, policy, memory, trace, and diagnostics views from safe endpoints", async () => {
    const responses: Record<string, unknown> = {
      "/control/snapshot": snapshot,
      "/control/marketplace/mcp": { schema_version: "1", entries: [{ server_id: "local-test-mcp", read_only_browse: true, install_allowed: false, launch_allowed: false }], read_only_browse: true, raw_payload_persisted: false },
      "/control/marketplace/skills": { schema_version: "1", entries: [{ skill_id: "test.safe_skill", script_execution_allowed: false, remote_loading_allowed: false }], previews: [{ skill_id: "test.safe_skill", preview: "Use deterministic local fixtures.", raw_instruction_persisted: false }], raw_payload_persisted: false },
      "/control/memory": { schema_version: "1", records: [{ memory_ref: "memory-1", content_preview: "User prefers concise status updates.", raw_transcript_persisted: false }], record_count: 1, raw_transcript_persisted: false },
      "/control/traces/search": { schema_version: "1", traces: [{ trace_id: "trace-1", status: "completed", raw_payload_persisted: false }], match_count: 1, truncated: false, raw_payload_persisted: false },
      "/control/approvals/history": { schema_version: "1", decisions: [], decision_count: 0, raw_payload_persisted: false },
      "/control/policies": { schema_version: "1", policies: [{ policy_id: "browser-actions", risk_level: "high", approval_required: true }], raw_payload_persisted: false },
      "/control/diagnostics": { schema_version: "1", runtime: "control_plane", status: "ok", remote_binding: false, raw_payload_persisted: false },
      "/control/connectors": { schema_version: "1", connectors: [{ connector_id: "github-connector", category: "github", account_action_allowed: false, auto_fetch_default_enabled: false }], connector_count: 1, raw_token_persisted: false },
      "/control/sources": { schema_version: "1", sources: [{ source_id: "source-github", connector_kind: "github", raw_credentials_persisted: false }], source_count: 1, raw_credentials_persisted: false },
      "/control/autofetch": { schema_version: "1", policies: [{ connector_id: "github-connector", control_state: "disabled", control_plane_toggle_allowed: true }], policy_count: 1, raw_payload_persisted: false },
      "/control/memory/tree/search": { schema_version: "1", query: "evidence", results: [{ node_id: "node-1", title: "Memory Tree Issue", evidence_count: 1, evidence_links: [{ chunk_id: "chunk-1", source_id: "source-github" }] }], raw_content_persisted: false },
      "/control/memory/tree/source/source-github": { schema_version: "1", tree: { source_id: "source-github", nodes: [{ node_id: "source-node-1", title: "GitHub Source", evidence_count: 1 }] }, raw_content_persisted: false },
      "/control/memory/tree/topic/memory-tree": { schema_version: "1", tree: { topic_id: "memory-tree", nodes: [{ node_id: "topic-node-1", title: "Memory Topic", evidence_count: 1 }] }, raw_content_persisted: false },
      "/control/memory/tree/daily/2026-05-18": { schema_version: "1", daily_digest: { node_id: "daily-2026-05-18", title: "Daily Digest", evidence_count: 1 }, raw_content_persisted: false },
      "/control/memory/tree/drill-down/chunk-1": { schema_version: "1", evidence: { chunk_id: "chunk-1", source_id: "source-github", quote_preview: "bounded evidence preview" } },
      "/control/memory/tree/scoring": { schema_version: "1", scores: [{ chunk_id: "chunk-1", importance: 0.7, decision: "keep", policy_owner: "MemoryTreeRuntime" }], score_count: 1, raw_content_persisted: false }
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      return new Response(JSON.stringify(responses[path]), { status: 200, headers: { "Content-Type": "application/json" } });
    }));

    renderApp();

    await userEvent.click(await screen.findByRole("button", { name: /MCP Marketplace/i }));
    expect(await screen.findByText("local-test-mcp")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Skills Marketplace/i }));
    expect((await screen.findAllByText("test.safe_skill")).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: /Memory Inspect/i }));
    expect(await screen.findByText("User prefers concise status updates.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Trace Search/i }));
    expect(await screen.findByText("trace-1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Tool Risk Policy/i }));
    expect(await screen.findByText("browser-actions")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Runtime Diagnostics/i }));
    expect(await screen.findByText("control_plane")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Connectors/i }));
    expect(await screen.findByText("github-connector")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Memory Sources/i }));
    expect(await screen.findByText("source-github")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Auto-Fetch/i }));
    expect(await screen.findByText("disabled")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Memory Trees/i }));
    expect(await screen.findByText("Memory Tree Issue")).toBeInTheDocument();
    expect(await screen.findByText("GitHub Source")).toBeInTheDocument();
    expect(await screen.findByText("Memory Topic")).toBeInTheDocument();
    expect((await screen.findAllByText("Daily Digest")).length).toBeGreaterThan(0);
    expect(await screen.findByText("bounded evidence preview")).toBeInTheDocument();
    expect(await screen.findByText("MemoryTreeRuntime")).toBeInTheDocument();
    expect(screen.queryByText(/apikey|Bearer|secret-token|raw prompt/i)).not.toBeInTheDocument();
  });

  it("shows protected API errors without exposing token text", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ message: "Local API authentication required." }), { status: 401, headers: { "Content-Type": "application/json" } })));

    renderApp();

    await waitFor(() => expect(screen.getByText("Control Plane unavailable")).toBeInTheDocument());
    expect(screen.queryByText(/Bearer/i)).not.toBeInTheDocument();
  });
});
