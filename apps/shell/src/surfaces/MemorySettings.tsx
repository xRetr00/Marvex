import { useCallback, useEffect, useMemo, useState } from "react";
import { BrainCircuit, Copy, Database, Network, RefreshCw, RotateCcw, Save, Server, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { controlRequest } from "@/lib/shellCommands";
import {
  defaultMemorySettings,
  loadMemorySettings,
  memorySettingsEnv,
  resetMemorySettings,
  saveMemorySettings,
  type GraphitiProvider,
  type MemoryBackend,
  type MemoryLlmClientKind,
  type MemoryLlmProvider,
  type MemorySettings as MemorySettingsState,
} from "@/lib/memorySettings";

type MemoryHealth = Record<string, unknown>;

export function MemorySettings() {
  const [settings, setSettings] = useState<MemorySettingsState>(() => loadMemorySettings());
  const [health, setHealth] = useState<MemoryHealth | null>(null);
  const [healthError, setHealthError] = useState("");
  const [saved, setSaved] = useState(false);

  const envPreview = useMemo(() => memorySettingsEnv(settings), [settings]);

  const loadHealth = useCallback(async () => {
    setHealthError("");
    try {
      const result = await controlRequest("/memory/health", "GET");
      setHealth(result && typeof result === "object" ? result as MemoryHealth : { status: String(result) });
    } catch (error) {
      setHealth(null);
      setHealthError(error instanceof Error ? error.message : "Memory health unavailable.");
    }
  }, []);

  useEffect(() => {
    void loadHealth();
  }, [loadHealth]);

  const update = <Key extends keyof MemorySettingsState>(key: Key, value: MemorySettingsState[Key]) => {
    setSaved(false);
    setSettings((current) => ({ ...current, [key]: value }));
  };

  const save = () => {
    setSettings(saveMemorySettings(settings));
    setSaved(true);
  };

  const reset = () => {
    setSettings(resetMemorySettings());
    setSaved(false);
  };

  const copyEnv = () => {
    void navigator.clipboard?.writeText(envPreview).catch(() => undefined);
  };

  return (
    <div style={page}>
      <header style={header}>
        <div style={{ minWidth: 0 }}>
          <h2 style={title}>Memories</h2>
          <p style={subtitle}>Graphiti, FalkorDB, Qdrant, retrieval, synthesis, context, and citation settings for the shell runtime.</p>
        </div>
        <div style={headerActions}>
          <Button size="sm" variant="outline" onClick={() => void loadHealth()}><RefreshCw size={14} />Refresh health</Button>
          <Button size="sm" variant="ghost" onClick={reset}><RotateCcw size={14} />Reset local defaults</Button>
          <Button size="sm" onClick={save}><Save size={14} />Save memory settings</Button>
        </div>
      </header>

      {saved ? <div style={notice}>Memory settings saved in Shell.</div> : null}

      <section style={grid2}>
        <Panel icon={<BrainCircuit size={16} />} title="Memory Runtime">
          <label style={field}>
            <span>Memory backend</span>
            <select aria-label="Memory backend" value={settings.backend} onChange={(event) => update("backend", event.target.value as MemoryBackend)} style={select}>
              <option value="graphiti_qdrant">Graphiti + Qdrant</option>
              <option value="disabled">Disabled</option>
            </select>
          </label>
          <label style={field}>
            <span>Namespace</span>
            <input aria-label="Memory namespace" value={settings.namespace} onChange={(event) => update("namespace", event.target.value)} style={input} />
          </label>
          <div style={chips}>
            {["retrieval", "summarization", "synthesis", "relevance ranking", "context injection", "user-visible answer", "source attribution", "user controls"].map((item) => (
              <Chip key={item} label={item} ok />
            ))}
          </div>
          <ToggleRow label="Require graph backend" checked={settings.graphRequired} onChange={(checked) => update("graphRequired", checked)} />
          <ToggleRow label="Require vector backend" checked={settings.vectorRequired} onChange={(checked) => update("vectorRequired", checked)} />
        </Panel>

        <Panel icon={<Network size={16} />} title="Graphiti">
          <label style={field}>
            <span>Graphiti provider</span>
            <select aria-label="Graphiti provider" value={settings.graphitiProvider} onChange={(event) => update("graphitiProvider", event.target.value as GraphitiProvider)} style={select}>
              <option value="falkordb">FalkorDB</option>
              <option value="neo4j">Neo4j</option>
            </select>
          </label>
          <label style={field}>
            <span>Graphiti LLM provider</span>
            <select aria-label="Graphiti LLM provider" value={settings.llmProvider} onChange={(event) => update("llmProvider", event.target.value as MemoryLlmProvider)} style={select}>
              <option value="lm_studio">LM Studio local</option>
              <option value="openai">OpenAI</option>
              <option value="custom_openai_compatible">Custom OpenAI-compatible</option>
            </select>
          </label>
          <label style={field}>
            <span>Graphiti LLM client</span>
            <select aria-label="Graphiti LLM client" value={settings.llmClientKind} onChange={(event) => update("llmClientKind", event.target.value as MemoryLlmClientKind)} style={select}>
              <option value="openai_generic">OpenAI-compatible chat completions</option>
              <option value="openai_responses">OpenAI Responses</option>
            </select>
          </label>
          <label style={field}>
            <span>Base URL</span>
            <input aria-label="Graphiti LLM base URL" value={settings.llmBaseUrl} onChange={(event) => update("llmBaseUrl", event.target.value)} style={input} />
          </label>
          <label style={field}>
            <span>Graphiti model</span>
            <input aria-label="Graphiti model" value={settings.llmModel} onChange={(event) => update("llmModel", event.target.value)} style={input} />
          </label>
          <label style={field}>
            <span>Small model</span>
            <input aria-label="Graphiti small model" value={settings.llmSmallModel} onChange={(event) => update("llmSmallModel", event.target.value)} style={input} />
          </label>
        </Panel>
      </section>

      <section style={grid2}>
        <Panel icon={<Server size={16} />} title="FalkorDB">
          <label style={field}>
            <span>Host or IP</span>
            <input aria-label="FalkorDB host" value={settings.falkorHost} onChange={(event) => update("falkorHost", event.target.value)} style={input} />
          </label>
          <label style={field}>
            <span>Port</span>
            <input aria-label="FalkorDB port" type="number" min={1} value={settings.falkorPort} onChange={(event) => update("falkorPort", Number(event.target.value))} style={input} />
          </label>
          <label style={field}>
            <span>Username</span>
            <input aria-label="FalkorDB username" value={settings.falkorUsername} onChange={(event) => update("falkorUsername", event.target.value)} style={input} />
          </label>
          <ToggleRow label="FalkorDB password saved outside Shell" checked={settings.falkorPasswordPresent} onChange={(checked) => update("falkorPasswordPresent", checked)} />
          <Endpoint value={`${settings.falkorHost}:${settings.falkorPort}`} />
        </Panel>

        <Panel icon={<Database size={16} />} title="Qdrant">
          <label style={field}>
            <span>Local path</span>
            <input aria-label="Qdrant path" value={settings.qdrantPath} onChange={(event) => update("qdrantPath", event.target.value)} style={input} />
          </label>
          <label style={field}>
            <span>Collection</span>
            <input aria-label="Qdrant collection" value={settings.qdrantCollection} onChange={(event) => update("qdrantCollection", event.target.value)} style={input} />
          </label>
          <label style={field}>
            <span>FastEmbed model</span>
            <input aria-label="Qdrant embedding model" value={settings.qdrantEmbeddingModel} onChange={(event) => update("qdrantEmbeddingModel", event.target.value)} style={input} />
          </label>
          <label style={field}>
            <span>Embedding base URL</span>
            <input aria-label="Embedding base URL" value={settings.embeddingBaseUrl} onChange={(event) => update("embeddingBaseUrl", event.target.value)} style={input} />
          </label>
          <label style={field}>
            <span>Embedding model</span>
            <input aria-label="Embedding model" value={settings.embeddingModel} onChange={(event) => update("embeddingModel", event.target.value)} style={input} />
          </label>
          <label style={field}>
            <span>Embedding dimension</span>
            <input aria-label="Embedding dimension" type="number" min={1} value={settings.embeddingDimension} onChange={(event) => update("embeddingDimension", Number(event.target.value))} style={input} />
          </label>
        </Panel>
      </section>

      <section style={grid2}>
        <Panel icon={<ShieldCheck size={16} />} title="Answer Injection">
          <label style={field}>
            <span>Retrieval limit</span>
            <input aria-label="Retrieval limit" type="number" min={1} value={settings.retrievalLimit} onChange={(event) => update("retrievalLimit", Number(event.target.value))} style={input} />
          </label>
          <label style={field}>
            <span>Context token budget</span>
            <input aria-label="Context token budget" type="number" min={1} value={settings.contextTokenBudget} onChange={(event) => update("contextTokenBudget", Number(event.target.value))} style={input} />
          </label>
          <label style={field}>
            <span>Reranker base URL</span>
            <input aria-label="Reranker base URL" value={settings.rerankerBaseUrl} onChange={(event) => update("rerankerBaseUrl", event.target.value)} style={input} />
          </label>
          <label style={field}>
            <span>Reranker model</span>
            <input aria-label="Reranker model" value={settings.rerankerModel} onChange={(event) => update("rerankerModel", event.target.value)} style={input} />
          </label>
          <ToggleRow label="Source attribution required" checked={settings.sourceAttributionRequired} onChange={(checked) => update("sourceAttributionRequired", checked)} />
          <ToggleRow label="User memory controls enabled" checked={settings.userControlsEnabled} onChange={(checked) => update("userControlsEnabled", checked)} />
        </Panel>

        <Panel icon={<Database size={16} />} title="Backend Health">
          {healthError ? <div style={notice}>{healthError}</div> : null}
          {health ? <HealthTable health={health} /> : <Muted>No health response yet.</Muted>}
          <div style={actions}>
            <Button size="sm" variant="outline" onClick={copyEnv}><Copy size={14} />Copy env</Button>
          </div>
          <pre style={codeBlock}>{envPreview}</pre>
        </Panel>
      </section>
    </div>
  );
}

function HealthTable({ health }: { health: MemoryHealth }) {
  const rows = flattenHealth(health).slice(0, 16);
  return (
    <div style={miniTable}>
      {rows.map(([key, value]) => (
        <div key={key} style={healthRow}>
          <span>{key}</span>
          <code>{String(value)}</code>
        </div>
      ))}
    </div>
  );
}

function flattenHealth(value: unknown, prefix = ""): Array<[string, string | number | boolean | null]> {
  if (!value || typeof value !== "object") return [[prefix || "status", String(value)]];
  return Object.entries(value as Record<string, unknown>).flatMap(([key, entry]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (entry && typeof entry === "object" && !Array.isArray(entry)) return flattenHealth(entry, nextKey);
    if (typeof entry === "string" || typeof entry === "number" || typeof entry === "boolean" || entry === null) return [[nextKey, entry]];
    return [[nextKey, JSON.stringify(entry)]];
  });
}

function Endpoint({ value }: { value: string }) {
  return <code style={endpoint}>falkor://{value}</code>;
}

function Panel({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section className="marvex-glass" style={panel}>
      <h3 style={panelTitle}>{icon}{title}</h3>
      {children}
    </section>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button type="button" aria-label={label} aria-pressed={checked} onClick={() => onChange(!checked)} style={{ ...toggleRow, borderColor: checked ? "color-mix(in srgb, var(--primary) 55%, var(--border))" : "var(--border)" }}>
      <span style={{ ...toggleDot, background: checked ? "var(--primary)" : "transparent", borderColor: checked ? "var(--primary)" : "var(--muted-foreground)" }} />
      <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
    </button>
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
const chips: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 6 };
const chip: React.CSSProperties = { border: "1px solid var(--border)", borderRadius: 999, padding: "3px 8px", background: "var(--secondary)", fontSize: 11 };
const actions: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8 };
const notice: React.CSSProperties = { border: "1px solid var(--primary)", color: "var(--foreground)", borderRadius: 8, padding: 10, fontSize: 12, background: "color-mix(in srgb, var(--primary) 10%, transparent)" };
const miniTable: React.CSSProperties = { display: "grid", gap: 6, fontSize: 12, minWidth: 0 };
const healthRow: React.CSSProperties = { display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: 8, alignItems: "center", borderBottom: "1px solid color-mix(in srgb, var(--border) 60%, transparent)", paddingBottom: 5 };
const endpoint: React.CSSProperties = { border: "1px solid var(--border)", borderRadius: 8, background: "var(--secondary)", color: "var(--foreground)", padding: "8px 10px", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" };
const codeBlock: React.CSSProperties = { margin: 0, maxHeight: 220, overflow: "auto", border: "1px solid var(--border)", borderRadius: 8, background: "var(--background)", color: "var(--muted-foreground)", padding: 10, fontSize: 11, lineHeight: 1.45 };
const toggleRow: React.CSSProperties = { display: "grid", gridTemplateColumns: "14px minmax(0, 1fr)", alignItems: "center", gap: 8, minWidth: 0, borderRadius: 8, border: "1px solid var(--border)", background: "color-mix(in srgb, var(--secondary) 70%, transparent)", color: "var(--foreground)", padding: "7px 9px", fontSize: 12, textAlign: "left", cursor: "pointer" };
const toggleDot: React.CSSProperties = { width: 10, height: 10, borderRadius: 999, border: "1px solid var(--muted-foreground)", boxShadow: "0 0 0 3px color-mix(in srgb, var(--primary) 10%, transparent)" };
