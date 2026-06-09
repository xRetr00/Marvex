import { useCallback, useEffect, useMemo, useState } from "react";
import { Copy, Database, ExternalLink, Eye, EyeOff, KeyRound, PlugZap, Plus, RefreshCw, Save, Search, Server, Trash2, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ModernLogViewer } from "@/components/marvex/ModernLogViewer";
import { controlRequest, openControlPlane, type LogTail } from "@/lib/shellCommands";
import { fetchDeps, installDep, type Dep } from "@/lib/depsClient";
import { fetchRuntimePolicy, setRuntimePolicyMode, type RuntimePolicy, type RuntimePolicyMode } from "@/lib/runtimePolicyClient";
import {
  fetchProviders,
  refreshProviderModels,
  removeProviderSecret,
  selectProviderAutomationModel,
  selectProvider,
  selectProviderModel,
  selectProviderMultiModels,
  setProviderConnection,
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

type WebSearchPayload = {
  schema_version?: string;
  primary_provider?: string;
  fallback_provider?: string;
  provider_order?: string[];
  searxng_base_url?: string;
};

export function ControlPlaneSettings() {
  const [providers, setProviders] = useState<ProviderCatalog | null>(null);
  const [deps, setDeps] = useState<Dep[]>([]);
  const [features, setFeatures] = useState<Record<string, boolean>>({});
  const [snapshot, setSnapshot] = useState<Snapshot>({});
  const [logs, setLogs] = useState<LogTail[]>([]);
  const [runtimePolicy, setRuntimePolicy] = useState<RuntimePolicy | null>(null);
  const [runtimeModeDraft, setRuntimeModeDraft] = useState<RuntimePolicyMode>("auto_marvex");
  const [mcp, setMcp] = useState<Record<string, unknown>[]>([]);
  const [skills, setSkills] = useState<Record<string, unknown>[]>([]);
  const [webSearch, setWebSearch] = useState<WebSearchPayload | null>(null);
  const [searxngUrlDraft, setSearxngUrlDraft] = useState("http://127.0.0.1:8888");
  const [keyDraft, setKeyDraft] = useState("");
  const [modelDraft, setModelDraft] = useState("");
  const [connectionUrlDraft, setConnectionUrlDraft] = useState("");
  const [providerModeDraft, setProviderModeDraft] = useState("native");
  const [automationModelDraft, setAutomationModelDraft] = useState("");
  const [multiModelDraft, setMultiModelDraft] = useState("");
  const [automationSupportsVision, setAutomationSupportsVision] = useState(false);
  const [automationVisionRequired, setAutomationVisionRequired] = useState(false);
  const [showKeyDraft, setShowKeyDraft] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeProvider = useMemo(() => {
    const rows = providers?.providers ?? [];
    return rows.find((row) => row.provider_id === providers?.active_provider_id) ?? rows[0] ?? null;
  }, [providers]);

  const load = useCallback(async () => {
    setError(null);
    const [providerResult, depsResult, snapshotResult, logsResult, runtimePolicyResult, mcpResult, skillsResult, webSearchResult] = await Promise.allSettled([
      fetchProviders(),
      fetchDeps(),
      controlRequest("/snapshot", "GET") as Promise<Snapshot>,
      controlRequest("/logs", "GET") as Promise<LogsPayload>,
      fetchRuntimePolicy(),
      controlRequest("/marketplace/mcp", "GET") as Promise<RegistryPayload>,
      controlRequest("/marketplace/skills", "GET") as Promise<RegistryPayload>,
      controlRequest("/web-search", "GET") as Promise<WebSearchPayload>,
    ]);
    if (providerResult.status === "fulfilled") setProviders(providerResult.value);
    else setError("Provider controls unavailable.");
    if (depsResult.status === "fulfilled") {
      setDeps(depsResult.value.deps);
      setFeatures(depsResult.value.features);
    }
    if (snapshotResult.status === "fulfilled") setSnapshot(snapshotResult.value);
    if (logsResult.status === "fulfilled") setLogs(logsResult.value.logs ?? []);
    if (runtimePolicyResult.status === "fulfilled") {
      setRuntimePolicy(runtimePolicyResult.value);
      setRuntimeModeDraft(runtimePolicyResult.value.mode);
    }
    if (mcpResult.status === "fulfilled") setMcp(mcpResult.value.entries ?? []);
    if (skillsResult.status === "fulfilled") setSkills(skillsResult.value.entries ?? []);
    if (webSearchResult.status === "fulfilled") {
      setWebSearch(webSearchResult.value);
      setSearxngUrlDraft(webSearchResult.value.searxng_base_url || "http://127.0.0.1:8888");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!activeProvider) return;
    setConnectionUrlDraft(activeProvider.base_url ?? "");
    setProviderModeDraft(activeProvider.provider_mode ?? "native");
    setAutomationModelDraft(activeProvider.automation_model || activeProvider.active_model || "");
    setMultiModelDraft((activeProvider.models ?? []).find((model) => !(activeProvider.multi_models ?? []).includes(model)) ?? activeProvider.models?.[0] ?? "");
    setAutomationSupportsVision(Boolean(activeProvider.automation_model_capabilities?.vision));
    setAutomationVisionRequired(Boolean(activeProvider.automation_policy?.vision_required));
  }, [activeProvider?.provider_id]);

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

  const installMcpServer = async (serverId: string) => {
    await controlRequest(`/marketplace/mcp/${encodeURIComponent(serverId)}/install`, "POST");
  };

  const onSelectProvider = (providerId: string) => void run("provider", () => selectProvider(providerId));
  const onSelectModel = (model: string) => {
    if (!activeProvider || !model.trim()) return;
    void run("model", () => selectProviderModel(activeProvider.provider_id, model.trim()));
  };
  const onAddModel = () => {
    if (!activeProvider || !modelDraft.trim()) return;
    const model = modelDraft.trim();
    setModelDraft("");
    void run("model", () => selectProviderModel(activeProvider.provider_id, model));
  };
  const onRefreshModels = () => {
    if (!activeProvider) return;
    void run("model discovery", () => refreshProviderModels(activeProvider.provider_id));
  };
  const onSaveConnection = () => {
    if (!activeProvider) return;
    void run("connection", () => setProviderConnection(activeProvider.provider_id, connectionUrlDraft.trim(), providerModeDraft));
  };
  const onSaveAutomationModel = () => {
    if (!activeProvider || !automationModelDraft.trim()) return;
    void run("automation model", () => selectProviderAutomationModel(activeProvider.provider_id, automationModelDraft.trim(), {
      supportsVision: automationSupportsVision,
      visionRequired: automationVisionRequired,
    }));
  };
  const onSaveRuntimePolicy = () => {
    void run("runtime policy", () => setRuntimePolicyMode(runtimeModeDraft));
  };
  const onSaveSearxngUrl = () => {
    void run("web search", async () => {
      const result = await controlRequest("/web-search", "POST", { searxng_base_url: searxngUrlDraft.trim() }) as WebSearchPayload;
      setWebSearch(result);
      setSearxngUrlDraft(result.searxng_base_url || searxngUrlDraft.trim());
      return result;
    });
  };
  const onAddMultiModel = () => {
    if (!activeProvider || !multiModelDraft) return;
    const current = new Set(activeProvider.multi_models ?? []);
    current.add(multiModelDraft);
    void run("multi models", () => selectProviderMultiModels(activeProvider.provider_id, [...current]));
  };
  const onRemoveMultiModel = (model: string) => {
    if (!activeProvider) return;
    const next = (activeProvider.multi_models ?? []).filter((item) => item !== model);
    void run("multi models", () => selectProviderMultiModels(activeProvider.provider_id, next));
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
  const onCopyMaskedKey = () => {
    const display = activeProvider?.secret_display;
    if (!display) return;
    void navigator.clipboard?.writeText(display).catch(() => undefined);
  };

  return (
    <div style={page}>
      <header style={header}>
        <div style={{ minWidth: 0 }}>
          <h2 style={title}>Settings</h2>
          <p style={subtitle}>Local runtime controls for providers, models, dependencies, MCP, skills, logs, traces, and telemetry.</p>
        </div>
        <div style={headerActions}>
          <Button size="sm" variant="outline" onClick={() => void openControlPlane()}><ExternalLink size={14} />Open full control plane</Button>
          <Button size="sm" variant="ghost" onClick={() => void load()} title="Refresh"><RefreshCw size={14} />Refresh</Button>
        </div>
      </header>
      {error && <div style={notice}>{error}</div>}

      <section style={grid2}>
        <Panel icon={<Server size={16} />} title="Provider stack">
          <label style={field}>
            <span>Active provider</span>
            <select aria-label="Active provider" value={providers?.active_provider_id ?? ""} onChange={(event) => onSelectProvider(event.target.value)} style={select}>
              {(providers?.providers ?? []).map((provider) => (
                <option key={provider.provider_id} value={provider.provider_id}>{provider.label ?? provider.provider_id}</option>
              ))}
            </select>
          </label>
          <strong style={subhead}>Model routing</strong>
          <div style={splitControls}>
            <label style={field}>
              <span>Active model</span>
              <select aria-label="Active model" value={activeProvider?.active_model ?? ""} onChange={(event) => onSelectModel(event.target.value)} style={select}>
                {(activeProvider?.models ?? []).map((model) => <option key={model} value={model}>{model}</option>)}
              </select>
            </label>
            <Button size="sm" variant="outline" onClick={onRefreshModels} disabled={!activeProvider || Boolean(busy)}><RefreshCw size={14} />Discover</Button>
          </div>
          <div style={inlineField}>
            <input aria-label="Add model" value={modelDraft} onChange={(event) => setModelDraft(event.target.value)} placeholder="Model id" style={input} />
            <Button aria-label="Add model" size="sm" variant="outline" onClick={onAddModel} disabled={!modelDraft.trim() || Boolean(busy)}><Plus size={14} /></Button>
          </div>
          <div style={modelList}>
            <div style={inlineField}>
              <label style={field}>
                <span>Multi models</span>
                <select aria-label="Multi-model candidate" value={multiModelDraft} onChange={(event) => setMultiModelDraft(event.target.value)} style={select}>
                  {(activeProvider?.models ?? []).map((model) => <option key={model} value={model}>{model}</option>)}
                </select>
              </label>
              <Button aria-label="Add multi-model" size="sm" variant="outline" onClick={onAddMultiModel} disabled={!activeProvider || !multiModelDraft || Boolean(busy)}><Plus size={14} /></Button>
            </div>
            {(activeProvider?.models ?? []).length === 0 ? <Muted>No models discovered yet.</Muted> : null}
            <div style={selectedModels}>
              {(activeProvider?.multi_models ?? []).length === 0 ? <Muted>No multi-models selected.</Muted> : (activeProvider?.multi_models ?? []).map((model) => (
                <span key={model} style={selectedModelChip}>
                  {model}
                  <button type="button" aria-label={`Remove multi-model ${model}`} onClick={() => onRemoveMultiModel(model)} style={chipRemoveButton}>
                    <Trash2 size={11} />
                  </button>
                </span>
              ))}
            </div>
          </div>
          <div style={providerRows}>
            {(providers?.providers ?? []).map((provider) => <ProviderTile key={provider.provider_id} provider={provider} active={provider.provider_id === providers?.active_provider_id} />)}
          </div>
        </Panel>

        <Panel icon={<Server size={16} />} title="Provider Endpoint">
          <label style={field}>
            <span>Provider mode</span>
            <select aria-label="Provider mode" value={providerModeDraft} onChange={(event) => setProviderModeDraft(event.target.value)} style={select}>
              <option value="litellm_sdk">LiteLLM SDK</option>
              <option value="litellm_openrouter">LiteLLM OpenRouter</option>
              <option value="litellm_proxy">LiteLLM proxy</option>
              <option value="openai_compatible">OpenAI-compatible URL</option>
              <option value="native">Native provider</option>
            </select>
          </label>
          <label style={field}>
            <span>Base URL</span>
            <input aria-label="Provider base URL" value={connectionUrlDraft} onChange={(event) => setConnectionUrlDraft(event.target.value)} placeholder="http://localhost:20128/v1" style={input} />
          </label>
          <div style={actions}>
            <Button size="sm" onClick={onSaveConnection} disabled={!activeProvider || Boolean(busy)}><Save size={14} />Save endpoint</Button>
          </div>
          <Muted>Use LiteLLM OpenRouter for OpenRouter keys. Use LiteLLM proxy only for a real LiteLLM proxy endpoint.</Muted>
        </Panel>
      </section>

      <section style={grid2}>
        <Panel icon={<Wrench size={16} />} title="Automation readiness">
          <label style={field}>
            <span>Automation model</span>
            <select aria-label="Automation model" value={automationModelDraft} onChange={(event) => setAutomationModelDraft(event.target.value)} style={select}>
              {automationModelDraft && !(activeProvider?.models ?? []).includes(automationModelDraft) && <option value={automationModelDraft}>{automationModelDraft}</option>}
              {(activeProvider?.models ?? []).map((model) => <option key={model} value={model}>{model}</option>)}
            </select>
          </label>
          <div style={inlineField}>
            <input aria-label="Automation model id" value={automationModelDraft} onChange={(event) => setAutomationModelDraft(event.target.value)} placeholder="Model for browser/computer use" style={input} />
            <Button aria-label="Save automation model" size="sm" onClick={onSaveAutomationModel} disabled={!automationModelDraft.trim() || Boolean(busy)}><Save size={14} /></Button>
          </div>
          <ModelToggleRow label="Selected automation model supports vision" checked={automationSupportsVision} onChange={setAutomationSupportsVision} />
          <ModelToggleRow label="Require vision for browser/computer tasks" checked={automationVisionRequired} onChange={setAutomationVisionRequired} />
          <Chip
            label={activeProvider?.automation_validation?.ready ? "automation ready" : activeProvider?.automation_validation?.reason_code ?? "automation not configured"}
            ok={Boolean(activeProvider?.automation_validation?.ready)}
          />
        </Panel>

        <Panel icon={<Wrench size={16} />} title="Runtime policy">
          <label style={field}>
            <span>Tool approval mode</span>
            <select aria-label="Tool approval mode" value={runtimeModeDraft} onChange={(event) => setRuntimeModeDraft(event.target.value as RuntimePolicyMode)} style={select}>
              <option value="auto_marvex">Auto Marvex</option>
              <option value="ask_before_risky">Ask before risky</option>
              <option value="owner_safe">Owner safe</option>
              <option value="locked_down">Locked down</option>
            </select>
          </label>
          <div style={actions}>
            <Button size="sm" onClick={onSaveRuntimePolicy} disabled={Boolean(busy) || runtimeModeDraft === runtimePolicy?.mode}><Save size={14} />Save mode</Button>
            <Chip label={runtimePolicy?.mode === "auto_marvex" ? "no approval prompts" : `active: ${runtimePolicy?.mode ?? "unknown"}`} ok={runtimePolicy?.mode === "auto_marvex"} />
          </div>
          <Muted>Auto Marvex runs model-authored tools without approval prompts for local debugging.</Muted>
        </Panel>

        <Panel icon={<Search size={16} />} title="Web search">
          <div style={chips}>
            <Chip label={`primary: ${webSearch?.primary_provider ?? "searxng"}`} ok />
            <Chip label={`fallback: ${webSearch?.fallback_provider ?? "ddgs"}`} ok />
          </div>
          <label style={field}>
            <span>SearXNG URL</span>
            <input aria-label="SearXNG URL" value={searxngUrlDraft} onChange={(event) => setSearxngUrlDraft(event.target.value)} placeholder="http://127.0.0.1:8888" style={input} />
          </label>
          <div style={actions}>
            <Button size="sm" onClick={onSaveSearxngUrl} disabled={!searxngUrlDraft.trim() || Boolean(busy)}><Save size={14} />Save SearXNG URL</Button>
            <Chip label={(webSearch?.provider_order ?? ["searxng", "ddgs"]).join(" -> ")} ok />
          </div>
        </Panel>
      </section>

      <section style={grid2}>
        <Panel icon={<KeyRound size={16} />} title="Credentials">
          <div style={secretState}>
            <span>Current key</span>
            <strong>{activeProvider?.secret_present ? (activeProvider.secret_display || "saved") : "not set"}</strong>
            <Button aria-label="Copy masked key" size="sm" variant="ghost" onClick={onCopyMaskedKey} disabled={!activeProvider?.secret_display}><Copy size={14} /></Button>
          </div>
          <label style={field}>
            <span>Provider API key</span>
            <div style={inlineField}>
              <input aria-label="Provider API key" value={keyDraft} onChange={(event) => setKeyDraft(event.target.value)} type={showKeyDraft ? "text" : "password"} placeholder="Paste key" style={input} />
              <Button aria-label={showKeyDraft ? "Hide key input" : "Show key input"} size="sm" variant="ghost" type="button" onClick={() => setShowKeyDraft((value) => !value)}>
                {showKeyDraft ? <EyeOff size={14} /> : <Eye size={14} />}
              </Button>
            </div>
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
                <div style={{ minWidth: 0 }}><strong>{dep.label}</strong><span>{dep.feature}</span></div>
                <Button size="sm" variant={dep.installed ? "ghost" : "outline"} disabled={dep.installed || Boolean(busy)} onClick={() => void run(`dep:${dep.id}`, () => installDep(dep.id))}>
                  {dep.installed ? "Installed" : `Install ${dep.label}`}
                </Button>
              </div>
            ))}
          </div>
        </Panel>

        <Panel icon={<PlugZap size={16} />} title="MCP / Skills Marketplaces">
          <div style={list}>
            {mcp
              .filter((row) => row.install_allowed === true && typeof row.required_dep_group_id === "string")
              .map((row) => {
                const depId = String(row.required_dep_group_id);
                const serverId = String(row.server_id ?? depId);
                return (
                  <div key={`mcp-install-${serverId}`} style={rowStyleCompact}>
                    <span>{serverId}</span>
                    <Button size="sm" variant="outline" disabled={Boolean(busy)} onClick={() => void run(`mcp:${depId}`, () => installDep(depId))}>
                      Install MCP dependency {depId}
                    </Button>
                    <Button size="sm" variant="outline" disabled={Boolean(busy)} onClick={() => void run(`mcp-server:${serverId}`, () => installMcpServer(serverId))}>
                      Install MCP server
                    </Button>
                  </div>
                );
              })}
          </div>
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
          <ModernLogViewer logs={logs} />
        </Panel>
      </section>
    </div>
  );
}

function ProviderTile({ provider, active }: { provider: ProviderRow; active: boolean }) {
  return (
    <div style={{ ...tile, borderColor: active ? "var(--primary)" : "var(--border)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
        <img alt="" src={`https://models.dev/logos/${provider.provider_id.split("_")[0]}.svg`} style={{ width: 16, height: 16, borderRadius: 999, filter: "invert(1)", opacity: 0.8 }} onError={(event) => { event.currentTarget.style.display = "none"; }} />
        <strong style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{provider.label ?? provider.provider_id}</strong>
      </div>
      <span>{provider.active_model || "no model"}</span>
      <Chip label={provider.healthy ? "healthy" : "check"} ok={Boolean(provider.healthy)} />
    </div>
  );
}

function ModelToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button type="button" aria-label={label} aria-pressed={checked} onClick={() => onChange(!checked)} style={{ ...toggleRow, borderColor: checked ? "color-mix(in srgb, var(--primary) 55%, var(--border))" : "var(--border)" }}>
      <span style={{ ...toggleDot, background: checked ? "var(--primary)" : "transparent", borderColor: checked ? "var(--primary)" : "var(--muted-foreground)" }} />
      <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
    </button>
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

const page: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 14, width: "min(1120px, 100%)", maxWidth: 1120, minWidth: 0, overflow: "hidden" };
const header: React.CSSProperties = { display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", minWidth: 0 };
const headerActions: React.CSSProperties = { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", justifyContent: "flex-end" };
const title: React.CSSProperties = { margin: 0, fontSize: 18, fontWeight: 750 };
const subtitle: React.CSSProperties = { margin: "3px 0 0", color: "var(--muted-foreground)", fontSize: 12 };
const grid2: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 14, minWidth: 0 };
const panel: React.CSSProperties = { borderRadius: 8, padding: 14, display: "flex", flexDirection: "column", gap: 12, minWidth: 0, overflow: "hidden" };
const panelTitle: React.CSSProperties = { margin: 0, display: "flex", gap: 8, alignItems: "center", fontSize: 13, fontWeight: 750 };
const field: React.CSSProperties = { display: "grid", gap: 5, fontSize: 12, color: "var(--muted-foreground)", minWidth: 0 };
const select: React.CSSProperties = { height: 34, minWidth: 0, borderRadius: 8, border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--foreground)", padding: "0 10px" };
const input: React.CSSProperties = { height: 34, minWidth: 0, width: "100%", borderRadius: 8, border: "1px solid var(--border)", background: "var(--background)", color: "var(--foreground)", padding: "0 10px" };
const splitControls: React.CSSProperties = { display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 8, alignItems: "end" };
const inlineField: React.CSSProperties = { display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 8, alignItems: "center", minWidth: 0 };
const providerRows: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8 };
const tile: React.CSSProperties = { display: "grid", gap: 7, borderRadius: 8, border: "1px solid var(--border)", padding: 10, background: "linear-gradient(180deg, color-mix(in srgb, var(--card) 88%, transparent), color-mix(in srgb, var(--secondary) 55%, transparent))", boxShadow: "var(--shadow-card)", fontSize: 12, minWidth: 0 };
const secretState: React.CSSProperties = { display: "grid", gridTemplateColumns: "auto minmax(0, 1fr) auto", gap: 8, alignItems: "center", fontSize: 12 };
const actions: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8 };
const chips: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 6 };
const chip: React.CSSProperties = { border: "1px solid var(--border)", borderRadius: 999, padding: "3px 8px", background: "var(--secondary)", fontSize: 11 };
const list: React.CSSProperties = { display: "grid", gap: 8 };
const row: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, border: "1px solid var(--border)", borderRadius: 8, padding: 9, fontSize: 12, minWidth: 0 };
const rowStyleCompact: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, fontSize: 12, minWidth: 0 };
const miniTable: React.CSSProperties = { display: "grid", gap: 6, fontSize: 12, minWidth: 0 };
const modelList: React.CSSProperties = { display: "grid", gap: 6, fontSize: 12 };
const selectedModels: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 6, minWidth: 0 };
const selectedModelChip: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 6, maxWidth: "100%", border: "1px solid var(--border)", borderRadius: 999, background: "var(--secondary)", color: "var(--foreground)", padding: "4px 6px 4px 9px", fontSize: 11 };
const chipRemoveButton: React.CSSProperties = { display: "grid", placeItems: "center", width: 18, height: 18, border: "1px solid var(--border)", borderRadius: 999, background: "var(--background)", color: "var(--muted-foreground)", cursor: "pointer" };
const toggleRow: React.CSSProperties = { display: "grid", gridTemplateColumns: "14px minmax(0, 1fr)", alignItems: "center", gap: 8, minWidth: 0, borderRadius: 8, border: "1px solid var(--border)", background: "color-mix(in srgb, var(--secondary) 70%, transparent)", color: "var(--foreground)", padding: "7px 9px", fontSize: 12, textAlign: "left", cursor: "pointer" };
const toggleDot: React.CSSProperties = { width: 10, height: 10, borderRadius: 999, border: "1px solid var(--muted-foreground)", boxShadow: "0 0 0 3px color-mix(in srgb, var(--primary) 10%, transparent)" };
const subhead: React.CSSProperties = { fontSize: 12 };
const notice: React.CSSProperties = { border: "1px solid var(--destructive)", color: "var(--destructive)", borderRadius: 8, padding: 10, fontSize: 12 };
