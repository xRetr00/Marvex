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
  agent_loops: [{ loop_id: "loop-1", step_count: 1, stop_reason: "waiting_for_human_approval", provider_tool_proposal_id: "proposal-1", pending_approval_count: 1, provider_continuation_ready: false, final_response_ready: false, result_status: "requires_human_approval", browser_action_count: 1, browser_action_kind: "click", mcp_tool_count: 0, risk_level: "high", safe_trace_ref: "trace-1", raw_payload_persisted: false }],
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
      "/control/memory/tree/scoring": { schema_version: "1", scores: [{ chunk_id: "chunk-1", importance: 0.7, decision: "keep", policy_owner: "MemoryTreeRuntime" }], score_count: 1, raw_content_persisted: false },
      "/control/voice": { schema_version: "1", summary: { main_stt_backend_id: "moonshine-v2", main_tts_backend_id: "kokoro-onnx", wakeword_enabled: false, no_raw_audio_persistence_by_default: true }, settings: { wakeword: { phrase: "Hey Marvex", always_listening_enabled: false }, vad: { backend: { main_backend_id: "silero-vad" } }, barge_in: { enabled: true }, early_speech: { enabled: true }, personality: { active_voice_id: "af_heart" } }, backends: { backend_health: [{ backend_id: "moonshine-v2", package_name: "moonshine-voice", import_available: true }, { backend_id: "kokoro-onnx", package_name: "kokoro-onnx", import_available: true }] }, telemetry: { wakeword_detections: 0, raw_audio_persisted: false, raw_transcript_persisted: false }, raw_audio_persisted: false, raw_transcript_persisted: false },
      "/control/voice/worker": { schema_version: "1", worker_id: "local-voice-worker", lifecycle_state: "stopped", process_started: false, heartbeat_ok: false, active_stt_backend_id: "moonshine-v2", active_tts_backend_id: "kokoro-onnx", active_voice_id: "af_heart", mic_status: "stopped", playback_status: "stopped", wakeword_status: "disabled", queued_tts_count: 0, local_only: true, hidden_recording_allowed: false, raw_audio_persisted: false, raw_transcript_persisted: false },
      "/control/voice/worker/devices": { schema_version: "1", input_devices: [{ device_id: "input-default", label: "Default microphone", is_input: true }], output_devices: [{ device_id: "output-default", label: "Default speaker", is_output: true }], raw_audio_persisted: false }
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
    await userEvent.click(screen.getByRole("button", { name: /Voice Runtime/i }));
    expect(await screen.findByText("Voice Worker Process")).toBeInTheDocument();
    expect(await screen.findByText("Default microphone")).toBeInTheDocument();
    expect((await screen.findAllByText("moonshine-v2")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText((content) => content.includes("Hey Marvex"))).length).toBeGreaterThan(0);
    expect(screen.queryByText(/apikey|Bearer|secret-token|raw prompt/i)).not.toBeInTheDocument();
  });

  it("shows protected API errors without exposing token text", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ message: "Local API authentication required." }), { status: 401, headers: { "Content-Type": "application/json" } })));

    renderApp();

    await waitFor(() => expect(screen.getByText("Control Plane unavailable")).toBeInTheDocument());
    expect(screen.queryByText(/Bearer/i)).not.toBeInTheDocument();
  });
});


describe("Control Plane runtime execution view", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders runtime execution panels from safe snapshot data without direct execution controls", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(snapshot), { status: 200, headers: { "Content-Type": "application/json" } })));

    renderApp();

    await userEvent.click(await screen.findByRole("button", { name: /Runtime Execution/i }));
    expect(await screen.findByText("Tool Calls / Provider Proposals")).toBeInTheDocument();
    expect(await screen.findByText("Browser Actions")).toBeInTheDocument();
    expect(await screen.findByText("MCP Calls")).toBeInTheDocument();
    expect(await screen.findByText("Provider Continuation")).toBeInTheDocument();
    expect(await screen.findByText("Final Response")).toBeInTheDocument();
    expect(await screen.findByText("pending_approval")).toBeInTheDocument();
    expect((await screen.findAllByText("not_ready")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/secret|Bearer|raw prompt|raw payload/i)).not.toBeInTheDocument();
  });
});

describe("Control Plane runtime policy view", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders autonomy mode selector, policy matrix, and audit records without executing tools", async () => {
    const policy = {
      schema_version: "1",
      mode: "auto_marvex",
      matrix: {
        web_search: "allow",
        browser_read_extract: "allow",
        browser_click_type: "ask",
        mcp_list: "allow",
        mcp_execute: "allow",
        mcp_install_launch: "ask",
        skills_use: "allow",
        skills_update_create: "allow",
        connectors_oauth: "ask",
        live_oauth_sync: "allow",
        auto_fetch: "allow",
        memory_auto_write: "allow",
        profile_write: "allow",
        semantic_memory_search: "allow",
        learning_mutation_candidates: "allow",
        provider_retry_fallback: "allow",
        file_read: "allow",
        file_write: "ask",
        file_delete: "ask",
        external_upload_send: "ask",
        shell_command_execution: "ask"
      },
      audit_records: [{ decision_id: "policy.auto.1", autonomy_mode: "auto_marvex", decision: "allow", action: "scheduled connector sync", resource_type: "connector", capability: "auto_fetch", reason_codes: ["policy.matrix.allow"], user_approval_state: "not_required", policy_source: "capability_runtime.autonomy", raw_payload_persisted: false }],
      hard_block_blacklist_only: true,
      read_list_search_allowed_by_default: true,
      side_effects_policy_controlled: true,
      raw_payload_persisted: false
    };
    const responses: Record<string, unknown> = {
      "/control/snapshot": snapshot,
      "/control/runtime-policy": policy,
      "/control/runtime-policy/audit": { schema_version: "1", audit_records: policy.audit_records, audit_count: 1, raw_payload_persisted: false },
      "/control/feedback": { schema_version: "1", events: [{ trace_id: "trace-feedback", signal_kind: "answer_rating", raw_feedback_persisted: false }], event_count: 1, raw_feedback_persisted: false },
      "/control/learning/candidates": { schema_version: "1", memory_candidates: [], skill_candidates: [{ candidate_id: "skill.feedback.1", summary: "Review skill candidate", review_required: true }], policy_candidates: [], preference_candidates: [], route_candidates: [], memory_scoring_changes: [{ memory_ref: "memory-1", useful: true, reason_code: "memory.feedback.useful" }], raw_feedback_persisted: false }
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (init?.method === "POST") return new Response(JSON.stringify({ ...policy, mode: "ask_before_risky", policy_update_started: true, execution_started: false }), { status: 200, headers: { "Content-Type": "application/json" } });
      return new Response(JSON.stringify(responses[path]), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    await userEvent.click(await screen.findByRole("button", { name: /Runtime Policy/i }));
    expect(await screen.findByText("Runtime Policy / Autonomy Modes")).toBeInTheDocument();
    expect(screen.getByLabelText("Autonomy mode")).toHaveValue("auto_marvex");
    expect(await screen.findByText("web_search")).toBeInTheDocument();
    expect((await screen.findAllByText("auto_fetch")).length).toBeGreaterThan(0);
    expect(await screen.findByText("mcp_execute")).toBeInTheDocument();
    expect(await screen.findByText("scheduled connector sync")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Autonomy mode"), "ask_before_risky");
    await userEvent.click(screen.getByRole("button", { name: /Feedback \/ Learning/i }));
    expect(await screen.findByText("Review skill candidate")).toBeInTheDocument();
    expect(await screen.findByText("memory.feedback.useful")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/control/runtime-policy"), expect.objectContaining({ method: "POST" }));
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/secret|Bearer|raw prompt|raw payload/i)).not.toBeInTheDocument();
  });
});
