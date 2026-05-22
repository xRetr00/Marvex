/**
 * Mode store: persists user's chosen mode (chat | overlay) to localStorage.
 * Only one mode is active at a time.
 */

export type AppMode = "chat" | "overlay";

const STORAGE_KEY = "marvex_app_mode";

export function getPersistedMode(): AppMode {
  try {
    const val = localStorage.getItem(STORAGE_KEY);
    if (val === "chat" || val === "overlay") return val;
  } catch {
    // localStorage unavailable
  }
  return "chat";
}

export function persistMode(mode: AppMode): void {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
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
