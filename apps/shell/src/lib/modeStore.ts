/**
 * Two top-level modes:
 *   - "chat":    the full chat window (the chat / test layer).
 *   - "overlay": the dynamic-island presence (Marvex like Siri in the OS).
 *                Cards and approvals live inside the island overlay.
 */

export type AppMode = "chat" | "overlay";

const MODE_KEY = "marvex_app_mode";

export function getPersistedMode(): AppMode {
  try {
    const val = localStorage.getItem(MODE_KEY);
    if (val === "chat" || val === "overlay") return val;
  } catch {
    // localStorage unavailable
  }
  return "chat";
}

export function persistMode(mode: AppMode): void {
  try {
    localStorage.setItem(MODE_KEY, mode);
  } catch {
    // ignore
  }
}

const SETUP_KEY = "marvex_setup_done";

export function isSetupDone(): boolean {
  try {
    return localStorage.getItem(SETUP_KEY) === "true";
  } catch {
    return false;
  }
}

export function markSetupDone(): void {
  try {
    localStorage.setItem(SETUP_KEY, "true");
  } catch {
    // ignore
  }
}
