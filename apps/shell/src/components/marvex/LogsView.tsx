import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { controlRequest, type LogTail } from "@/lib/shellCommands";
import { Button } from "@/components/ui/button";
import { ModernLogViewer } from "./ModernLogViewer";

type LogsApiResponse = {
  schema_version: string;
  logs: LogTail[];
  raw_log_payload_persisted: false;
};

/** Read-only Logs / Traces / Telemetry board. All data comes from the
 * authenticated Control Plane API; the shell UI never reads log files itself. */
export function LogsView() {
  const [logs, setLogs] = useState<LogTail[]>([]);
  const [traces, setTraces] = useState<Record<string, unknown>[]>([]);
  const [telemetry, setTelemetry] = useState<Record<string, unknown>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const [lg, snap] = await Promise.allSettled([controlRequest("/logs", "GET"), controlRequest("/snapshot", "GET")]);
      if (cancelled) return;
      setApiError(null);
      if (lg.status === "fulfilled" && lg.value && typeof lg.value === "object") {
        const payload = lg.value as LogsApiResponse;
        setLogs(Array.isArray(payload.logs) ? payload.logs : []);
      } else if (lg.status === "rejected") {
        setLogs([]);
        setApiError("Control Plane logs API unavailable.");
      }
      if (snap.status === "fulfilled" && snap.value && typeof snap.value === "object") {
        const s = snap.value as { traces?: Record<string, unknown>[]; telemetry?: Record<string, unknown> };
        setTraces(Array.isArray(s.traces) ? s.traces : []);
        setTelemetry(s.telemetry ?? {});
      } else if (snap.status === "rejected") {
        setTraces([]);
        setTelemetry({});
        setApiError("Control Plane snapshot API unavailable.");
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [reload]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>Logs / Traces / Telemetry</h2>
        <Button size="sm" variant="ghost" onClick={() => setReload((n) => n + 1)}><RefreshCw size={14} /></Button>
      </div>

      <section className="marvex-glass" style={{ borderRadius: 8, padding: 14 }}>
        <h3 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 750, color: "var(--foreground)" }}>Runtime signals</h3>
        {Object.keys(telemetry).length === 0 ? <Muted>No telemetry.</Muted> : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 6 }}>
            {Object.entries(telemetry).slice(0, 24).map(([k, v]) => (
              <div key={k} style={{ fontSize: 11, padding: "8px 10px", borderRadius: 8, background: "linear-gradient(180deg, var(--secondary), color-mix(in srgb, var(--card) 70%, transparent))", border: "1px solid var(--border)", boxShadow: "var(--shadow-card)" }}>
                <div style={{ color: "var(--muted-foreground)" }}>{k.replace(/_/g, " ")}</div>
                <div style={{ fontWeight: 600 }}>{typeof v === "object" ? JSON.stringify(v) : String(v)}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="marvex-glass" style={{ borderRadius: 8, padding: 14 }}>
        <h3 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 750, color: "var(--foreground)" }}>Trace cards</h3>
        {traces.length === 0 ? <Muted>No trace projections.</Muted> : (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {traces.slice(0, 30).map((t, i) => (
              <code key={i} style={{ fontSize: 11, fontFamily: "ui-monospace, monospace", color: "var(--foreground)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", border: "1px solid var(--border)", borderRadius: 8, padding: "7px 9px", background: "var(--background)" }}>
                {JSON.stringify(t)}
              </code>
            ))}
          </div>
        )}
      </section>

      {apiError ? <Muted>{apiError}</Muted> : <ModernLogViewer logs={logs} />}
    </div>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>{children}</span>;
}
