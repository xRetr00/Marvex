import { useEffect, useState } from "react";
import { getSetupStatus, getSupervisorStatus, controlRequest } from "./shellCommands";

export type WakewordState = "unknown" | "running" | "enabled" | "not_ready" | "disabled";

export interface BackendStatus {
  phase: string;
  ready: boolean;
  launched: boolean;
  services: Record<string, string>;
  wakeword: WakewordState;
}

export const FAILED_PHASES = new Set([
  "venv_failed",
  "install_failed",
  "install_incomplete",
  "uv_unavailable",
  "failed",
]);

export function serviceOk(value: string): boolean {
  return value.startsWith("running") || value === "ready" || value === "dev";
}

export async function fetchBackendStatus(): Promise<BackendStatus> {
  const [setup, services, voice] = await Promise.allSettled([
    getSetupStatus(),
    getSupervisorStatus(),
    controlRequest("/voice/worker", "GET"),
  ]);
  const svc = services.status === "fulfilled" ? services.value : {};
  let wakeword: WakewordState = "unknown";
  if (voice.status === "fulfilled" && voice.value && typeof voice.value === "object") {
    const w = voice.value as { wakeword_status?: string; lifecycle_state?: string };
    if (w.wakeword_status) wakeword = w.wakeword_status as WakewordState;
    else if (w.lifecycle_state === "running") wakeword = "running";
  } else if (typeof svc.voice_worker === "string" && svc.voice_worker.startsWith("running")) {
    wakeword = "running";
  }
  return {
    phase: setup.status === "fulfilled" ? setup.value.runtime_phase : "unknown",
    ready: setup.status === "fulfilled" ? setup.value.ready : false,
    launched: setup.status === "fulfilled" ? setup.value.launched : false,
    services: svc,
    wakeword,
  };
}

/** Poll backend readiness — fast while booting, slow once ready. */
export function useBackendStatus(): BackendStatus | null {
  const [status, setStatus] = useState<BackendStatus | null>(null);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      const next = await fetchBackendStatus();
      if (cancelled) return;
      setStatus(next);
      timer = setTimeout(() => void tick(), next.ready ? 5000 : 1200);
    };
    void tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);
  return status;
}
