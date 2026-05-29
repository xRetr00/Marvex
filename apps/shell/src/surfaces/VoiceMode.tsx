import { useEffect, useMemo, useState } from "react";
import type { ButtonHTMLAttributes, ReactNode, CSSProperties } from "react";
import { Download, Mic, MicOff, Play, Radio, RefreshCw, Volume2 } from "lucide-react";
import {
  downloadVoiceModelGroup,
  fetchVoiceModelCatalog,
  fetchVoiceWorkerStatus,
  startVoiceWorker,
  stopVoiceWorker,
  switchVoiceWorkerStt,
  switchVoiceWorkerTts,
  switchVoiceWorkerVoice,
  testVoiceWorkerStt,
  testVoiceWorkerTts,
  type VoiceModelCatalogAsset,
  type VoiceWorkerStatus
} from "@/lib/voiceControlClient";

type ModelDownloadState = {
  state: "downloading" | "complete" | "failed";
  completed: number;
  total: number;
  error?: string;
};

export function VoiceMode() {
  const [status, setStatus] = useState<VoiceWorkerStatus | null>(null);
  const [catalog, setCatalog] = useState<VoiceModelCatalogAsset[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [downloads, setDownloads] = useState<Record<string, ModelDownloadState>>({});
  const [message, setMessage] = useState("Loading voice worker...");

  const load = async () => {
    const [nextStatus, nextCatalog] = await Promise.all([fetchVoiceWorkerStatus(), fetchVoiceModelCatalog()]);
    setStatus(nextStatus);
    setCatalog(nextCatalog.assets ?? []);
    setMessage("Voice worker control is connected.");
  };

  useEffect(() => {
    let cancelled = false;
    void Promise.all([fetchVoiceWorkerStatus(), fetchVoiceModelCatalog()])
      .then(([nextStatus, nextCatalog]) => {
        if (cancelled) return;
        setStatus(nextStatus);
        setCatalog(nextCatalog.assets ?? []);
        setMessage("Voice worker control is connected.");
      })
      .catch(() => {
        if (!cancelled) setMessage("Voice worker control is unavailable.");
      });
    return () => { cancelled = true; };
  }, []);

  const required = useMemo(() => status?.model_assets?.required ?? [], [status]);
  const catalogByModel = useMemo(() => {
    const map = new Map<string, VoiceModelCatalogAsset[]>();
    for (const asset of catalog) {
      const assets = map.get(asset.model_id) ?? [];
      assets.push(asset);
      map.set(asset.model_id, assets);
    }
    return map;
  }, [catalog]);
  const sttOptions = useMemo(() => {
    return optionList(catalog.filter((asset) => asset.model_kind === "stt").map((asset) => asset.model_id), status?.active_stt_backend_id ?? "moonshine-v2");
  }, [catalog, status?.active_stt_backend_id]);
  const ttsOptions = useMemo(() => {
    return optionList(catalog.filter((asset) => asset.model_kind === "tts_voice").map((asset) => asset.backend_id), status?.active_tts_backend_id ?? "kokoro-onnx");
  }, [catalog, status?.active_tts_backend_id]);
  const voiceOptions = useMemo(() => {
    return optionList(catalog.filter((asset) => asset.model_kind === "tts_voice").map((asset) => asset.model_id), status?.active_voice_id ?? "af_heart");
  }, [catalog, status?.active_voice_id]);

  const run = async (label: string, action: () => Promise<unknown>) => {
    setBusy(label);
    try {
      await action();
      await load();
      setMessage(`${label} requested.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : `${label} failed.`);
    } finally {
      setBusy(null);
    }
  };

  const runModelDownload = async (modelId: string, assets: VoiceModelCatalogAsset[]) => {
    const label = `Download ${modelId}`;
    setBusy(label);
    setDownloads((current) => ({ ...current, [modelId]: { state: "downloading", completed: 0, total: assets.length } }));
    setMessage(`Downloading ${modelId} 0/${assets.length}.`);
    try {
      await downloadVoiceModelGroup(assets, (event) => {
        setDownloads((current) => ({ ...current, [modelId]: { state: "downloading", completed: event.completed, total: event.total } }));
        setMessage(`Downloading ${modelId} ${event.completed}/${event.total}.`);
      });
      await load();
      setDownloads((current) => ({ ...current, [modelId]: { state: "complete", completed: assets.length, total: assets.length } }));
      setMessage(`${label} requested.`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : `${label} failed.`;
      setDownloads((current) => ({ ...current, [modelId]: { state: "failed", completed: current[modelId]?.completed ?? 0, total: assets.length, error: errorMessage } }));
      setMessage(errorMessage);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 920 }}>
      <section style={panelStyle}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>Voice Mode</h2>
            <p style={{ margin: "4px 0 0", color: "var(--muted-foreground)", fontSize: 12 }}>{message}</p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <IconButton label="Refresh voice status" disabled={Boolean(busy)} onClick={() => void run("Refresh", load)}><RefreshCw size={15} /></IconButton>
            <IconButton label={status?.process_started ? "Stop voice worker" : "Start voice worker"} disabled={Boolean(busy)} onClick={() => void run(status?.process_started ? "Stop voice worker" : "Start voice worker", status?.process_started ? stopVoiceWorker : startVoiceWorker)}>
              {status?.process_started ? <MicOff size={15} /> : <Mic size={15} />}
            </IconButton>
          </div>
        </div>
      </section>

      <section style={gridStyle}>
        <SelectField label="STT model" value={status?.active_stt_backend_id ?? "moonshine-v2"} options={sttOptions} onChange={(value) => void run("Switch STT", () => switchVoiceWorkerStt(value))} />
        <SelectField label="TTS library" value={status?.active_tts_backend_id ?? "kokoro-onnx"} options={ttsOptions} onChange={(value) => void run("Switch TTS", () => switchVoiceWorkerTts(value))} />
        <SelectField label="Voice" value={status?.active_voice_id ?? "af_heart"} options={voiceOptions} onChange={(value) => void run("Switch voice", () => switchVoiceWorkerVoice(value))} />
      </section>

      <section style={gridStyle}>
        <StatusTile icon={<Radio size={16} />} label="Wake word" value={String(status?.wakeword_status ?? "unknown")} detail={String(status?.wakeword_model_status?.readiness_blocker ?? status?.wakeword_model_status?.exact_blocker ?? "ready")} />
        <StatusTile icon={<Mic size={16} />} label="STT" value={String(status?.stt_backend_status?.status ?? "unknown")} detail={String(status?.stt_backend_status?.exact_blocker ?? "ready")} />
        <StatusTile icon={<Volume2 size={16} />} label="TTS" value={String(status?.tts_backend_status?.status ?? "unknown")} detail={String(status?.tts_backend_status?.exact_blocker ?? "ready")} />
      </section>

      <section style={panelStyle}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: "var(--foreground)" }}>Model Assets</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <TextButton className="marvex-test-btn" disabled={Boolean(busy)} onClick={() => void run("Test STT", testVoiceWorkerStt)}>
              <Play size={13} /> Test STT
            </TextButton>
            <TextButton className="marvex-test-btn marvex-test-btn-primary" disabled={Boolean(busy)} onClick={() => void run("Test TTS", () => testVoiceWorkerTts())}>
              <Volume2 size={13} /> Test TTS
            </TextButton>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {required.map((asset) => {
            const modelId = String(asset.model_id ?? "");
            const modelKind = String(asset.model_kind ?? "");
            const downloadTargets = catalogTargetsFor(asset, catalogByModel, catalog);
            const downloadState = downloads[modelId];
            const statusLabel = downloadState?.state === "downloading"
              ? `${downloadState.completed}/${downloadState.total} files`
              : downloadState?.state === "failed"
                ? "failed"
                : downloadState?.state === "complete" || String(asset.status ?? "") === "installed"
                  ? "installed"
                  : String(asset.status ?? "unknown");
            const detail = downloadState?.error ?? String(asset.exact_blocker ?? "ready");
            const isInstalled = String(asset.status ?? "") === "installed" || downloadState?.state === "complete";
            const disabled = downloadTargets.length === 0 || Boolean(busy) || isInstalled;
            const kindLabel = modelKind.includes("stt") ? "STT" : modelKind.includes("tts_voice") ? "TTS" : modelKind.includes("wakeword") || modelKind.includes("kws") ? "WW" : modelKind.toUpperCase().slice(0, 3) || "ML";
            return (
              <div key={`${modelId}-${String(asset.backend_id ?? "")}`} className="marvex-asset-row">
                <span className={`marvex-asset-kind-badge marvex-asset-kind-${kindLabel.toLowerCase()}`}>{kindLabel}</span>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 650 }}>{modelId}</div>
                  <div style={{ color: "var(--muted-foreground)", fontSize: 11, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {String(asset.backend_id ?? "")} &middot; {detail} &middot; {downloadTargets.length || 0} files
                  </div>
                </div>
                <TextButton
                  aria-label={`Download ${modelId}`}
                  disabled={disabled}
                  className={isInstalled ? "marvex-asset-installed" : undefined}
                  onClick={() => void runModelDownload(modelId, downloadTargets)}
                >
                  {isInstalled ? null : <Download size={13} />} {statusLabel}
                </TextButton>
              </div>
            );
          })}
          {required.length === 0 && <span style={{ color: "var(--muted-foreground)", fontSize: 12 }}>No voice assets reported.</span>}
        </div>
      </section>
    </div>
  );
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: Array<{ id: string; label: string }>; onChange: (value: string) => void }) {
  return (
    <label style={{ ...panelStyle, gap: 8, display: "flex", flexDirection: "column" }}>
      <span style={{ color: "var(--muted-foreground)", fontSize: 12, fontWeight: 650 }}>{label}</span>
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} style={selectStyle}>
        {options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
      </select>
    </label>
  );
}

function optionList(values: Array<string | undefined>, active: string): Array<{ id: string; label: string }> {
  const ids = new Set<string>();
  if (active) ids.add(active);
  for (const value of values) {
    const normalized = String(value ?? "").trim();
    if (normalized) ids.add(normalized);
  }
  return [...ids].map((id) => ({ id, label: id }));
}

function catalogTargetsFor(
  required: Record<string, unknown>,
  catalogByModel: Map<string, VoiceModelCatalogAsset[]>,
  catalog: VoiceModelCatalogAsset[],
): VoiceModelCatalogAsset[] {
  const modelId = String(required.model_id ?? "");
  const exact = catalogByModel.get(modelId);
  if (exact?.length) return exact;
  const backendId = String(required.backend_id ?? "");
  const modelKind = String(required.model_kind ?? "");
  return catalog.filter((asset) => asset.backend_id === backendId && asset.model_kind === modelKind);
}

function statusDot(value: string) {
  const v = value.toLowerCase();
  if (v === "ready" || v === "enabled" || v === "running" || v === "installed") return "#34d399";
  if (v === "stopped" || v === "failed" || v === "error") return "#e54d2e";
  return "#f59e0b";
}

function StatusTile({ icon, label, value, detail }: { icon: ReactNode; label: string; value: string; detail: string }) {
  const dot = statusDot(value);
  return (
    <div className="marvex-voice-tile">
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span className="marvex-voice-tile-icon">{icon}</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--muted-foreground)", letterSpacing: "0.02em", textTransform: "uppercase" }}>{label}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 10 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: dot, flexShrink: 0, boxShadow: `0 0 6px ${dot}88` }} />
        <span style={{ fontWeight: 700, fontSize: 15 }}>{value}</span>
      </div>
      <div style={{ marginTop: 5, color: "var(--muted-foreground)", fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{detail}</div>
    </div>
  );
}

function IconButton({ label, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button aria-label={label} title={label} style={iconButtonStyle} {...props}>{children}</button>;
}

function TextButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} style={{ ...textButtonStyle, ...(props.style ?? {}) }} />;
}

const panelStyle: CSSProperties = {
  background: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 14,
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
  gap: 12,
};

const selectStyle: CSSProperties = {
  width: "100%",
  height: 38,
  borderRadius: 8,
  border: "1px solid var(--border)",
  background: "var(--secondary)",
  color: "var(--foreground)",
  padding: "0 10px",
};

const iconButtonStyle: CSSProperties = {
  width: 36,
  height: 36,
  borderRadius: 8,
  border: "1px solid var(--border)",
  background: "var(--secondary)",
  color: "var(--foreground)",
  display: "grid",
  placeItems: "center",
  cursor: "pointer",
};

const textButtonStyle: CSSProperties = {
  minHeight: 34,
  borderRadius: 8,
  border: "1px solid var(--border)",
  background: "var(--secondary)",
  color: "var(--foreground)",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 6,
  padding: "0 10px",
  cursor: "pointer",
  fontSize: 12,
  whiteSpace: "nowrap",
};

const assetRowStyle: CSSProperties = {
  minHeight: 56,
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: "9px 10px",
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  alignItems: "center",
  gap: 10,
  background: "var(--muted)",
};
