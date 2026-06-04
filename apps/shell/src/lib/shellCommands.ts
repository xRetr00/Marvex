import { invoke, listen } from "./tauriBridge";

export type ShellRuntimeConfig = {
  core_base_url: string;
  control_base_url: string;
  auth_token_present: boolean;
  token_value_logged: false;
};

export async function getShellRuntimeConfig(): Promise<ShellRuntimeConfig> {
  return invoke<ShellRuntimeConfig>("shell_runtime_config");
}

/** Map of service name -> status string (includes the "runtime" bootstrap phase). */
export type SupervisorStatus = Record<string, string>;

export async function getSupervisorStatus(): Promise<SupervisorStatus> {
  return invoke<SupervisorStatus>("supervisor_status");
}

export type SetupStatus = {
  schema_version: string;
  runtime_phase: string;
  ready: boolean;
  launched: boolean;
  services: Record<string, string>;
  manifest: unknown | null;
};

/** Structured first-run status: runtime bootstrap phase + services + ready flag. */
export async function getSetupStatus(): Promise<SetupStatus> {
  return invoke<SetupStatus>("get_setup_status");
}

/** Re-attempt the runtime bootstrap (no-op once services are running). */
export async function startSetup(): Promise<SetupStatus> {
  return invoke<SetupStatus>("start_setup");
}

/** Alias of startSetup for "start the backend" call sites. */
export async function startBackend(): Promise<SetupStatus> {
  return invoke<SetupStatus>("start_backend");
}

export type BackendHealth = {
  reachable: boolean;
  status_code?: number;
  health?: unknown;
  error?: string;
};

/** Core daemon health (loopback /health). */
export async function getBackendHealth(): Promise<BackendHealth> {
  return invoke<BackendHealth>("backend_health");
}

export type GuiHealth = {
  schema_version: string;
  component: string;
  status: string;
  services_running: number;
  runtime_phase: string;
};

/** GUI/shell process health. */
export async function getGuiHealth(): Promise<GuiHealth> {
  return invoke<GuiHealth>("gui_health");
}

export type ChatTurnMetadata = {
  agent_profile_id?: string;
  persona_profile_id?: string;
  selected_voice_id?: string;
  session_id?: string;
};

export async function submitChatTurn(
  text: string,
  metadata?: ChatTurnMetadata,
  previousResponseId?: string,
): Promise<unknown> {
  return invoke("submit_chat_turn", { text, metadata, previousResponseId });
}

/** A live tool-activity frame from the core's streaming turn (chain-of-thought). */
export type ChatToolEvent = {
  type: "tool";
  phase?: "start" | "end";
  id?: string;
  name?: string;
  arguments?: string;
  state?: string;
};

export type ChatStatusEvent = {
  type: "status";
  status?: string;
  detail?: string;
  trace_id?: string;
};

export type ChatCommentaryEvent = {
  type: "commentary";
  text?: string;
  trace_id?: string;
};

type ChatStreamEvent = {
  turn_id: string;
  event:
    | { type: "delta"; text?: string }
    | { type: "final"; result?: unknown }
    | { type: "error"; message?: string; reason?: string }
    | ChatToolEvent
    | ChatStatusEvent
    | ChatCommentaryEvent;
};

export interface ChatStreamHandlers {
  onDelta: (chunk: string) => void;
  /** Live tool-activity steps for the unified Chain-of-Thought UI. */
  onTool?: (event: ChatToolEvent) => void;
  /** Safe runtime lifecycle commentary such as thinking or searching. */
  onStatus?: (event: ChatStatusEvent) => void;
  /** Model-authored user-visible text emitted before a tool call. */
  onCommentary?: (event: ChatCommentaryEvent) => void;
}

/**
 * Streaming chat turn (docs/TODO/06). Subscribes to the `chat-stream` Tauri
 * event, forwards each text delta to `onDelta` and each tool frame to `onTool`,
 * and resolves with the terminal AssistantTurnResult. Single in-flight turn is
 * assumed (the UI gates on `pending`), so the global `chat-stream` listener
 * needs no per-turn filtering. Accepts a bare `onDelta` callback for backward
 * compatibility, or a handlers object to also receive tool events.
 */
export async function submitChatTurnStream(
  text: string,
  metadata: ChatTurnMetadata | undefined,
  previousResponseId: string | undefined,
  handlers: ((chunk: string) => void) | ChatStreamHandlers,
): Promise<unknown> {
  const resolved: ChatStreamHandlers =
    typeof handlers === "function" ? { onDelta: handlers } : handlers;
  const unlisten = await listen<ChatStreamEvent>("chat-stream", (message) => {
    const event = message.payload?.event;
    if (!event) return;
    if (event.type === "delta" && typeof event.text === "string") {
      resolved.onDelta(event.text);
    } else if (event.type === "tool") {
      resolved.onTool?.(event);
    } else if (event.type === "status") {
      resolved.onStatus?.(event);
    } else if (event.type === "commentary") {
      resolved.onCommentary?.(event);
    }
  });
  try {
    return await invoke("submit_chat_turn_stream", { text, metadata, previousResponseId });
  } finally {
    unlisten();
  }
}

export async function cancelActiveChatTurn(): Promise<{ schema_version: string; cancel_requested: boolean }> {
  return invoke("cancel_active_chat_turn");
}

export async function resumeApprovalTurn(args: {
  text: string;
  traceId: string;
  turnId: string;
  approvalId: string;
  decision: "approve" | "deny" | "cancel";
}): Promise<unknown> {
  return invoke("resume_approval_turn", args);
}

export type BackendSessionRef = {
  ref_type: "session";
  ref_id: string;
};

export type BackendSession = {
  schema_version: string;
  session_ref: BackendSessionRef;
  title: string;
  created_at_unix_ms: number;
  updated_at_unix_ms: number;
  turn_count: number;
  trace_count: number;
  transcript_persisted: false;
};

export async function createChatSession(title?: string): Promise<{ schema_version: string; session: BackendSession; transcript_persisted: false }> {
  return invoke("create_chat_session", { title });
}

export async function listChatSessions(): Promise<{ schema_version: string; sessions: BackendSession[]; session_count: number; transcript_persisted: false }> {
  return invoke("list_chat_sessions");
}

export async function renameChatSession(sessionId: string, title: string): Promise<unknown> {
  return controlRequest(`/sessions/${encodeURIComponent(sessionId)}`, "PATCH", { title });
}

export async function deleteChatSession(sessionId: string): Promise<unknown> {
  return controlRequest(`/sessions/${encodeURIComponent(sessionId)}`, "DELETE");
}

export async function controlPlaneEntryUrl(): Promise<string> {
  return invoke<string>("control_plane_entry_url");
}

export async function controlRequest(path: string, method = "GET", body?: unknown): Promise<unknown> {
  return invoke("control_request", { path, method, body });
}

export type OverlayWindowSize = {
  width: number;
  height: number;
};

export async function setOverlaySize({ width, height }: OverlayWindowSize, radius?: number): Promise<void> {
  await invoke("set_overlay_size", { width, height, radius: radius ?? null });
}

export async function showChat(): Promise<void> {
  await invoke("show_chat");
}

export async function showOverlay(): Promise<void> {
  await invoke("show_overlay");
}

export async function openControlPlane(): Promise<void> {
  await invoke("open_control_plane");
}

export async function marvexShutdown(): Promise<void> {
  await invoke("marvex_shutdown");
}

export async function marvexRestart(): Promise<void> {
  await invoke("marvex_restart");
}

export type LogTail = { name: string; source?: string; lines: string[] };
