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
  "wheelhouse_missing",
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
    wakeword = wakewordStateFromVoiceStatus(voice.value as Record<string, unknown>);
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

function wakewordStateFromVoiceStatus(status: Record<string, unknown>): WakewordState {
  const wakewordStatus = typeof status.wakeword_status === "string" ? status.wakeword_status : undefined;
  const lifecycleState = typeof status.lifecycle_state === "string" ? status.lifecycle_state : undefined;
  const modelStatus = status.wakeword_model_status && typeof status.wakeword_model_status === "object"
    ? status.wakeword_model_status as Record<string, unknown>
    : {};
  const supervisorStatus = status.wakeword_supervisor_status && typeof status.wakeword_supervisor_status === "object"
    ? status.wakeword_supervisor_status as Record<string, unknown>
    : {};
  const readiness = typeof modelStatus.readiness_status === "string"
    ? modelStatus.readiness_status
    : typeof modelStatus.status === "string"
      ? modelStatus.status
      : undefined;

  if (wakewordStatus === "disabled") return "disabled";
  if (readiness === "not_ready" || supervisorStatus.asset_ready === false) return "not_ready";
  if (wakewordStatus === "running" || wakewordStatus === "enabled" || wakewordStatus === "not_ready") return wakewordStatus;
  if (lifecycleState === "running") return "running";
  return "unknown";
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
