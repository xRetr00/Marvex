type TauriInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;
type TauriListen = <T>(event: string, handler: (event: { payload: T }) => void) => Promise<() => void>;

declare global {
  interface Window {
    __TAURI__?: {
      core?: { invoke: TauriInvoke };
      event?: { listen: TauriListen };
    };
  }
}

export async function invoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  const bridge = window.__TAURI__?.core?.invoke;
  if (!bridge) throw new Error("Tauri bridge unavailable.");
  return bridge<T>(command, args);
}

export async function listen<T>(event: string, handler: (event: { payload: T }) => void): Promise<() => void> {
  const bridge = window.__TAURI__?.event?.listen;
  if (!bridge) return () => undefined;
  return bridge<T>(event, handler);
}
