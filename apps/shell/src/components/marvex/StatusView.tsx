import { useEffect, useState } from "react";
import { controlRequest } from "@/lib/shellCommands";
import { serviceOk, type BackendStatus } from "@/lib/backendStatus";

/** Read-only "quick info" status board: Marvex, workers/daemons, voice, deps,
 * provider/LLM, persona/agent. Purely informational — no controls (those live in
 * the Control Plane window). */
export function StatusView({ backend }: { backend: BackendStatus | null }) {
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null);
  const [agents, setAgents] = useState<Record<string, unknown> | null>(null);
  const [personas, setPersonas] = useState<Record<string, unknown> | null>(null);
  const [voice, setVoice] = useState<Record<string, unknown> | null>(null);
  const [deps, setDeps] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const [snap, ag, pe, vo, de] = await Promise.allSettled([
        controlRequest("/snapshot", "GET"),
        controlRequest("/agents", "GET"),
        controlRequest("/personas", "GET"),
        controlRequest("/voice/worker", "GET"),
        controlRequest("/deps", "GET"),
      ]);
      if (cancelled) return;
      if (snap.status === "fulfilled") setSnapshot(snap.value as Record<string, unknown>);
      if (ag.status === "fulfilled") setAgents(ag.value as Record<string, unknown>);
      if (pe.status === "fulfilled") setPersonas(pe.value as Record<string, unknown>);
      if (vo.status === "fulfilled") setVoice(vo.value as Record<string, unknown>);
      if (de.status === "fulfilled") setDeps(de.value as Record<string, unknown>);
    };
    void load();
    const t = setInterval(() => void load(), 4000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  const services = backend?.services ?? {};
  const workerNames = Object.keys(services).filter((n) => n !== "runtime");
  const voiceWorkerProcessRunning = serviceOk(String(services.voice_worker ?? ""));
  const providers = Array.isArray((snapshot as { providers?: unknown[] } | null)?.providers) ? (snapshot as { providers: Record<string, unknown>[] }).providers : [];
  const settings = (snapshot as { settings?: Record<string, unknown> } | null)?.settings ?? {};
  const telemetry = (snapshot as { telemetry?: Record<string, unknown> } | null)?.telemetry ?? {};
  const activeAgent = (agents as { active_agent_id?: string } | null)?.active_agent_id ?? "—";
  const activePersona = (personas as { active_persona_id?: string } | null)?.active_persona_id ?? "—";
  const depsList = Array.isArray((deps as { deps?: unknown[] } | null)?.deps) ? (deps as { deps: Record<string, unknown>[] }).deps : [];
  const features = (deps as { features?: Record<string, boolean> } | null)?.features ?? {};

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 760 }}>
      <Card title="Marvex">
        <Row label="Runtime phase" value={backend?.phase ?? "…"} ok={backend?.ready} />
        <Row label="Ready" value={backend?.ready ? "yes" : "no"} ok={backend?.ready} />
        <Row label="Launched" value={backend?.launched ? "yes" : "no"} ok={backend?.launched} />
      </Card>

      <Card title="Workers / Daemons">
        {workerNames.length === 0 && <Muted>No services reported.</Muted>}
        {workerNames.map((name) => (
          <Row key={name} label={name.replace(/_/g, " ")} value={services[name]} ok={serviceOk(services[name])} />
        ))}
      </Card>

      <Card title="Voice / Wake word">
        <Row label="Wake word" value={String((voice as { wakeword_status?: string } | null)?.wakeword_status ?? backend?.wakeword ?? "unknown")} ok={backend?.wakeword === "running" || backend?.wakeword === "enabled"} />
        <Row label="Lifecycle" value={voiceLifecycleLabel(voice, voiceWorkerProcessRunning)} ok={voiceWorkerProcessRunning || Boolean((voice as { process_started?: boolean } | null)?.process_started)} />
        <Row label="STT backend" value={String((voice as { active_stt_backend_id?: string } | null)?.active_stt_backend_id ?? "—")} />
        <Row label="TTS backend" value={String((voice as { active_tts_backend_id?: string } | null)?.active_tts_backend_id ?? "—")} />
        <Row label="Active voice" value={String((voice as { active_voice_id?: string } | null)?.active_voice_id ?? "—")} />
      </Card>

      <Card title="Provider / LLM">
        {providers.length === 0 && <Muted>No providers reported.</Muted>}
        {providers.map((p, i) => (
          <Row key={i} label={String(p.provider_id ?? p.id ?? `provider ${i + 1}`)} value={String(p.active_model ?? p.model ?? p.status ?? "—")} ok={Boolean(p.healthy)} />
        ))}
        <Row label="Default model" value={String((settings as { default_model?: string }).default_model ?? "—")} />
      </Card>

      <Card title="Persona / Agent">
        <Row label="Active agent" value={activeAgent} />
        <Row label="Active persona" value={activePersona} />
      </Card>

      <Card title="Dependencies">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: depsList.length ? 8 : 0 }}>
          {Object.entries(features).map(([k, v]) => (
            <span key={k} style={{ fontSize: 11, padding: "3px 8px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--secondary)", color: v ? "var(--foreground)" : "var(--muted-foreground)" }}>
              {k}: {v ? "ok" : "missing"}
            </span>
          ))}
          {Object.keys(features).length === 0 && <Muted>No dependency info.</Muted>}
        </div>
        {depsList.map((d, i) => (
          <Row key={i} label={String(d.label ?? d.id ?? `dep ${i + 1}`)} value={d.installed ? "installed" : "not installed"} ok={Boolean(d.installed)} />
        ))}
      </Card>

      <Card title="Telemetry (summary)">
        {Object.keys(telemetry).length === 0 && <Muted>No telemetry summary.</Muted>}
        {Object.entries(telemetry).slice(0, 12).map(([k, v]) => (
          <Row key={k} label={k.replace(/_/g, " ")} value={typeof v === "object" ? JSON.stringify(v) : String(v)} />
        ))}
      </Card>
    </div>
  );
}

function voiceLifecycleLabel(voice: Record<string, unknown> | null, processRunning: boolean) {
  const lifecycle = String((voice as { lifecycle_state?: string } | null)?.lifecycle_state ?? "—");
  if (lifecycle === "stopped" && processRunning) return "process running";
  return lifecycle;
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ background: "var(--card)", borderRadius: 14, padding: 16, border: "1px solid var(--border)" }}>
      <h2 style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 700, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{title}</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>{children}</div>
    </section>
  );
}

function Row({ label, value, ok }: { label: string; value: unknown; ok?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, fontSize: 12 }}>
      <span style={{ color: "var(--muted-foreground)", textTransform: "capitalize" }}>{label}</span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontWeight: 500, maxWidth: "60%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {ok !== undefined && <span style={{ width: 7, height: 7, borderRadius: "50%", background: ok ? "#34d399" : "#e54d2e" }} />}
        {String(value ?? "—")}
      </span>
    </div>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>{children}</span>;
}
