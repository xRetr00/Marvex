import { useCallback, useEffect, useMemo, useState } from "react";
import { Database, KeyRound, PlugZap, RefreshCw, Save, Server, Trash2, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { controlRequest, type LogTail } from "@/lib/shellCommands";
import { fetchDeps, installDep, type Dep } from "@/lib/depsClient";
import {
  fetchProviders,
  removeProviderSecret,
  selectProvider,
  selectProviderModel,
  setProviderSecret,
  type ProviderCatalog,
  type ProviderRow,
} from "@/lib/providerControlClient";

type Snapshot = {
  traces?: Record<string, unknown>[];
  telemetry?: Record<string, unknown>;
};

type LogsPayload = {
  logs?: LogTail[];
};

type RegistryPayload = {
  entries?: Record<string, unknown>[];
};

export function ControlPlaneSettings() {
  const [providers, setProviders] = useState<ProviderCatalog | null>(null);
  const [deps, setDeps] = useState<Dep[]>([]);
  const [features, setFeatures] = useState<Record<string, boolean>>({});
  const [snapshot, setSnapshot] = useState<Snapshot>({});
  const [logs, setLogs] = useState<LogTail[]>([]);
  const [mcp, setMcp] = useState<Record<string, unknown>[]>([]);
  const [skills, setSkills] = useState<Record<string, unknown>[]>([]);
  const [keyDraft, setKeyDraft] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeProvider = useMemo(() => {
    const rows = providers?.providers ?? [];
    return rows.find((row) => row.provider_id === providers?.active_provider_id) ?? rows[0] ?? null;
  }, [providers]);

  const load = useCallback(async () => {
    setError(null);
    const [providerResult, depsResult, snapshotResult, logsResult, mcpResult, skillsResult] = await Promise.allSettled([
      fetchProviders(),
      fetchDeps(),
      controlRequest("/snapshot", "GET") as Promise<Snapshot>,
      controlRequest("/logs", "GET") as Promise<LogsPayload>,
      controlRequest("/marketplace/mcp", "GET") as Promise<RegistryPayload>,
      controlRequest("/marketplace/skills", "GET") as Promise<RegistryPayload>,
    ]);
    if (providerResult.status === "fulfilled") setProviders(providerResult.value);
    else setError("Provider controls unavailable.");
    if (depsResult.status === "fulfilled") {
      setDeps(depsResult.value.deps);
      setFeatures(depsResult.value.features);
    }
    if (snapshotResult.status === "fulfilled") setSnapshot(snapshotResult.value);
    if (logsResult.status === "fulfilled") setLogs(logsResult.value.logs ?? []);
    if (mcpResult.status === "fulfilled") setMcp(mcpResult.value.entries ?? []);
    if (skillsResult.status === "fulfilled") setSkills(skillsResult.value.entries ?? []);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (label: string, action: () => Promise<unknown>) => {
    setBusy(label);
    setError(null);
    try {
      const result = await action();
      if (result && typeof result === "object" && "providers" in result) setProviders(result as ProviderCatalog);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label} failed`);
    } finally {
      setBusy(null);
    }
  };

  const onSelectProvider = (providerId: string) => void run("provider", () => selectProvider(providerId));
  const onSelectModel = (model: string) => {
    if (!activeProvider) return;
    void run("model", () => selectProviderModel(activeProvider.provider_id, model));
  };
  const onSaveKey = () => {
    if (!activeProvider || !keyDraft.trim()) return;
    const secret = keyDraft.trim();
    setKeyDraft("");
    void run("secret", () => setProviderSecret(activeProvider.provider_id, secret));
  };
  const onRemoveKey = () => {
    if (!activeProvider) return;
    void run("secret", () => removeProviderSecret(activeProvider.provider_id));
  };

  return (
    <div style={page}>
      <header style={header}>
        <div>
          <h2 style={title}>Settings</h2>
          <p style={subtitle}>Local runtime controls for providers, models, dependencies, MCP, skills, logs, traces, and telemetry.</p>
        </div>
        <Button size="sm" variant="ghost" onClick={() => void load()} title="Refresh"><RefreshCw size={14} /></Button>
      </header>
      {error && <div style={notice}>{error}</div>}

      <section style={grid2}>
        <Panel icon={<Server size={16} />} title="Providers / Models">
          <label style={field}>
            <span>Active provider</span>
            <select aria-label="Active provider" value={providers?.active_provider_id ?? ""} onChange={(event) => onSelectProvider(event.target.value)} style={select}>
              {(providers?.providers ?? []).map((provider) => (
                <option key={provider.provider_id} value={provider.provider_id}>{provider.label ?? provider.provider_id}</option>
              ))}
            </select>
          </label>
          <label style={field}>
            <span>Active model</span>
            <select aria-label="Active model" value={activeProvider?.active_model ?? ""} onChange={(event) => onSelectModel(event.target.value)} style={select}>
              {(activeProvider?.models ?? []).map((model) => <option key={model} value={model}>{model}</option>)}
            </select>
          </label>
          <div style={providerRows}>
            {(providers?.providers ?? []).map((provider) => <ProviderTile key={provider.provider_id} provider={provider} active={provider.provider_id === providers?.active_provider_id} />)}
          </div>
        </Panel>

        <Panel icon={<KeyRound size={16} />} title="Credentials">
          <div style={secretState}>
            <span>Current key</span>
            <strong>{activeProvider?.secret_present ? (activeProvider.secret_display || "********") : "not set"}</strong>
          </div>
          <label style={field}>
            <span>Provider API key</span>
            <input aria-label="Provider API key" value={keyDraft} onChange={(event) => setKeyDraft(event.target.value)} type="password" placeholder="Paste key" style={input} />
          </label>
          <div style={actions}>
            <Button size="sm" onClick={onSaveKey} disabled={!keyDraft.trim() || Boolean(busy)}><Save size={14} />Save key</Button>
            <Button size="sm" variant="outline" onClick={onRemoveKey} disabled={!activeProvider?.secret_present || Boolean(busy)}><Trash2 size={14} />Remove key</Button>
          </div>
        </Panel>
      </section>

      <section style={grid2}>
        <Panel icon={<Wrench size={16} />} title="Dependencies">
          <div style={chips}>{Object.entries(features).map(([name, ok]) => <Chip key={name} label={`${name}: ${ok ? "ok" : "missing"}`} ok={ok} />)}</div>
          <div style={list}>
            {deps.map((dep) => (
              <div key={dep.id} style={row}>
                <div><strong>{dep.label}</strong><span>{dep.feature}</span></div>
                <Button size="sm" variant={dep.installed ? "ghost" : "outline"} disabled={dep.installed || Boolean(busy)} onClick={() => void run(`dep:${dep.id}`, () => installDep(dep.id))}>
                  {dep.installed ? "Installed" : `Install ${dep.label}`}
                </Button>
              </div>
            ))}
          </div>
        </Panel>

        <Panel icon={<PlugZap size={16} />} title="MCP / Skills Marketplaces">
          <MiniTable title="MCP" rows={mcp} primaryKey="server_id" />
          <MiniTable title="Skills" rows={skills} primaryKey="skill_id" />
        </Panel>
      </section>

      <section style={grid2}>
        <Panel icon={<Database size={16} />} title="Telemetry / Traces">
          <div style={chips}>{Object.entries(snapshot.telemetry ?? {}).map(([key, value]) => <Chip key={key} label={`${key}: ${String(value)}`} ok />)}</div>
          <MiniTable title="Traces" rows={snapshot.traces ?? []} primaryKey="trace_id" />
        </Panel>
        <Panel icon={<Database size={16} />} title="Logs">
          {logs.length === 0 ? <Muted>No logs exposed yet.</Muted> : logs.map((log) => (
            <div key={log.name} style={logBlock}>
              <strong>{log.name}</strong>
              <pre>{log.lines.slice(-12).join("\n")}</pre>
            </div>
          ))}
        </Panel>
      </section>
    </div>
  );
}

function ProviderTile({ provider, active }: { provider: ProviderRow; active: boolean }) {
  return (
    <div style={{ ...tile, borderColor: active ? "var(--primary)" : "var(--border)" }}>
      <strong>{provider.label ?? provider.provider_id}</strong>
      <span>{provider.active_model || "no model"}</span>
      <Chip label={provider.healthy ? "healthy" : "check"} ok={Boolean(provider.healthy)} />
    </div>
  );
}

function Panel({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section className="marvex-glass" style={panel}>
      <h3 style={panelTitle}>{icon}{title}</h3>
      {children}
    </section>
  );
}

function MiniTable({ title, rows, primaryKey }: { title: string; rows: Record<string, unknown>[]; primaryKey: string }) {
  return (
    <div style={miniTable}>
      <strong>{title}</strong>
      {rows.length === 0 ? <Muted>No data.</Muted> : rows.slice(0, 8).map((row, index) => (
        <code key={`${String(row[primaryKey] ?? index)}`}>{String(row[primaryKey] ?? JSON.stringify(row))}</code>
      ))}
    </div>
  );
}

function Chip({ label, ok }: { label: string; ok: boolean }) {
  return <span style={{ ...chip, color: ok ? "var(--foreground)" : "var(--muted-foreground)" }}>{label}</span>;
}

function Muted({ children }: { children: React.ReactNode }) {
  return <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>{children}</span>;
}

const page: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 14, maxWidth: 1120 };
const header: React.CSSProperties = { display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" };
const title: React.CSSProperties = { margin: 0, fontSize: 18, fontWeight: 750 };
const subtitle: React.CSSProperties = { margin: "3px 0 0", color: "var(--muted-foreground)", fontSize: 12 };
const grid2: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 14 };
const panel: React.CSSProperties = { borderRadius: 8, padding: 14, display: "flex", flexDirection: "column", gap: 12 };
const panelTitle: React.CSSProperties = { margin: 0, display: "flex", gap: 8, alignItems: "center", fontSize: 13, fontWeight: 750 };
const field: React.CSSProperties = { display: "grid", gap: 5, fontSize: 12, color: "var(--muted-foreground)" };
const select: React.CSSProperties = { height: 34, borderRadius: 8, border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--foreground)", padding: "0 10px" };
const input: React.CSSProperties = { height: 34, borderRadius: 8, border: "1px solid var(--border)", background: "var(--background)", color: "var(--foreground)", padding: "0 10px" };
const providerRows: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8 };
const tile: React.CSSProperties = { display: "grid", gap: 5, borderRadius: 8, border: "1px solid var(--border)", padding: 10, background: "color-mix(in srgb, var(--card) 80%, transparent)", fontSize: 12 };
const secretState: React.CSSProperties = { display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12 };
const actions: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8 };
const chips: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 6 };
const chip: React.CSSProperties = { border: "1px solid var(--border)", borderRadius: 999, padding: "3px 8px", background: "var(--secondary)", fontSize: 11 };
const list: React.CSSProperties = { display: "grid", gap: 8 };
const row: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, border: "1px solid var(--border)", borderRadius: 8, padding: 9, fontSize: 12 };
const miniTable: React.CSSProperties = { display: "grid", gap: 6, fontSize: 12 };
const logBlock: React.CSSProperties = { display: "grid", gap: 6, fontSize: 12 };
const notice: React.CSSProperties = { border: "1px solid var(--destructive)", color: "var(--destructive)", borderRadius: 8, padding: 10, fontSize: 12 };
