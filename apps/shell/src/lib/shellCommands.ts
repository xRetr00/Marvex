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

export async function submitChatTurn(text: string): Promise<unknown> {
  return invoke("submit_chat_turn", { text });
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

export async function showChat(): Promise<void> {
  await invoke("show_chat");
}
