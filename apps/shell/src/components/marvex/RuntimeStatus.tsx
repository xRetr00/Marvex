import { useEffect, useState } from "react";
import { getSetupStatus, getBackendHealth, getSupervisorStatus, type SetupStatus } from "@/lib/shellCommands";

const PHASE_LABEL: Record<string, string> = {
  "creating environment": "Creating runtime environment",
  "installing packages": "Installing runtime packages (first launch)",
  ready: "Runtime ready",
  dev: "Dev runtime (uv run)",
  unknown: "Starting runtime...",
  uv_unavailable: "uv unavailable",
};

function phaseLabel(phase: string): string {
  return PHASE_LABEL[phase] ?? phase.replace(/_/g, " ");
}

function isWorking(phase: string): boolean {
  return phase === "creating environment" || phase === "installing packages" || phase === "unknown";
}

interface RuntimeSnapshot {
  setup: SetupStatus | null;
  coreReachable: boolean | null;
  services: Record<string, string>;
}

/**
 * Live, real-data view of what the backend is actually doing — runtime
 * bootstrap phase, Core reachability, and per-service status. Surfaces *why*
 * deps may be slow to load instead of leaving the user staring at a spinner.
 */
export function RuntimeStatus() {
  const [snap, setSnap] = useState<RuntimeSnapshot>({ setup: null, coreReachable: null, services: {} });

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const [setup, health, services] = await Promise.allSettled([
        getSetupStatus(),
        getBackendHealth(),
        getSupervisorStatus(),
      ]);
      if (cancelled) return;
      setSnap({
        setup: setup.status === "fulfilled" ? setup.value : null,
        coreReachable: health.status === "fulfilled" ? health.value.reachable : null,
        services: services.status === "fulfilled" ? services.value : {},
      });
    };
    void poll();
    const interval = setInterval(() => void poll(), 2000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const phase = snap.setup?.runtime_phase ?? "unknown";
  const working = isWorking(phase);
  const serviceEntries = Object.entries(snap.services).filter(([name]) => name !== "runtime");
  const runningCount = serviceEntries.filter(([, s]) => s.startsWith("running")).length;

  const dotColor = snap.coreReachable === true ? "#34d399" : snap.coreReachable === false ? "#e54d2e" : "#b4b4b4";

  return (
    <div className="marvex-glass" style={{ display: "flex", flexDirection: "column", gap: 10, padding: 14, borderRadius: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ position: "relative", width: 9, height: 9 }}>
            <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: dotColor }} />
            {working && <span style={{ position: "absolute", inset: -3, borderRadius: "50%", border: `2px solid ${dotColor}`, opacity: 0.4, animation: "marvex-ping 1.4s ease-out infinite" }} />}
          </span>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--foreground)" }}>{phaseLabel(phase)}</span>
        </div>
        <span style={{ fontSize: 11, color: "var(--muted-foreground)" }}>
          Core {snap.coreReachable === true ? "reachable" : snap.coreReachable === false ? "unreachable" : "—"} · {runningCount}/{serviceEntries.length || "?"} services
        </span>
      </div>

      {serviceEntries.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {serviceEntries.map(([name, status]) => {
            const ok = status.startsWith("running");
            const err = status.startsWith("spawn_error") || status.startsWith("exited") || status.includes("error");
            const color = ok ? "#34d399" : err ? "#e54d2e" : "#fbbf24";
            return (
              <span key={name} title={status} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, padding: "3px 8px", borderRadius: 999, background: "var(--card)", border: "1px solid var(--border)", color: "var(--muted-foreground)" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: color }} />
                <span style={{ textTransform: "capitalize" }}>{name}</span>
              </span>
            );
          })}
        </div>
      )}

      {working && (
        <p style={{ margin: 0, fontSize: 11, color: "var(--muted-foreground)" }}>
          First launch builds a Python runtime with uv — this can take a few minutes. Dependency data appears once Core is reachable.
        </p>
      )}
    </div>
  );
}

export default RuntimeStatus;
