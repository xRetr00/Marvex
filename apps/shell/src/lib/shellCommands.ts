import { invoke } from "./tauriBridge";

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

export async function submitChatTurn(text: string, metadata?: ChatTurnMetadata): Promise<unknown> {
  return invoke("submit_chat_turn", { text, metadata });
}

export async function controlRequest(path: string, method = "GET", body?: unknown): Promise<unknown> {
  return invoke("control_request", { path, method, body });
}

export async function setOverlayClickThrough(ignore: boolean): Promise<void> {
  await invoke("set_overlay_click_through", { ignore });
}

export async function showSpotlight(): Promise<void> {
  await invoke("show_spotlight");
}

export async function hideSpotlight(): Promise<void> {
  await invoke("hide_spotlight");
}

export async function showChat(): Promise<void> {
  await invoke("show_chat");
}

export async function showOverlay(): Promise<void> {
  await invoke("show_overlay");
}
