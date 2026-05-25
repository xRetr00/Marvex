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

const STT_MODELS = [
  { id: "moonshine-v2", label: "Moonshine v2" },
  { id: "sensevoice-small", label: "SenseVoice Small" },
  { id: "sherpa-onnx-asr", label: "Sherpa ONNX ASR" }
];

const TTS_LIBS = [
  { id: "kokoro-onnx", label: "Kokoro ONNX" },
  { id: "piper-tts", label: "Piper TTS" },
  { id: "sherpa-onnx-tts", label: "Sherpa ONNX TTS" }
];

const VOICES = [
  { id: "af_heart", label: "Kokoro AF Heart" },
  { id: "piper-default", label: "Piper Default" },
  { id: "sherpa-voice", label: "Sherpa Voice" }
];

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
        <SelectField label="STT model" value={status?.active_stt_backend_id ?? "moonshine-v2"} options={STT_MODELS} onChange={(value) => void run("Switch STT", () => switchVoiceWorkerStt(value))} />
        <SelectField label="TTS library" value={status?.active_tts_backend_id ?? "kokoro-onnx"} options={TTS_LIBS} onChange={(value) => void run("Switch TTS", () => switchVoiceWorkerTts(value))} />
        <SelectField label="Voice" value={status?.active_voice_id ?? "af_heart"} options={VOICES} onChange={(value) => void run("Switch voice", () => switchVoiceWorkerVoice(value))} />
      </section>

      <section style={gridStyle}>
        <StatusTile icon={<Radio size={16} />} label="Wake word" value={String(status?.wakeword_status ?? "unknown")} detail={String(status?.wakeword_model_status?.readiness_blocker ?? status?.wakeword_model_status?.exact_blocker ?? "ready")} />
        <StatusTile icon={<Mic size={16} />} label="STT" value={String(status?.stt_backend_status?.status ?? "unknown")} detail={String(status?.stt_backend_status?.exact_blocker ?? "ready")} />
        <StatusTile icon={<Volume2 size={16} />} label="TTS" value={String(status?.tts_backend_status?.status ?? "unknown")} detail={String(status?.tts_backend_status?.exact_blocker ?? "ready")} />
      </section>

      <section style={panelStyle}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 10 }}>
          <h3 style={{ margin: 0, fontSize: 13, textTransform: "uppercase", letterSpacing: 0, color: "var(--muted-foreground)" }}>Model Assets</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <TextButton disabled={Boolean(busy)} onClick={() => void run("Test STT", testVoiceWorkerStt)}><Play size={14} /> Test STT</TextButton>
            <TextButton disabled={Boolean(busy)} onClick={() => void run("Test TTS", () => testVoiceWorkerTts())}><Volume2 size={14} /> Test TTS</TextButton>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {required.map((asset) => {
            const modelId = String(asset.model_id ?? "");
            const downloadTargets = catalogByModel.get(modelId) ?? [];
            const downloadState = downloads[modelId];
            const statusLabel = downloadState?.state === "downloading"
              ? `Downloading ${downloadState.completed}/${downloadState.total}`
              : downloadState?.state === "failed"
                ? "failed"
                : downloadState?.state === "complete"
                  ? "installed"
                  : String(asset.status ?? "unknown");
            const detail = downloadState?.error ?? String(asset.exact_blocker ?? "ready");
            const disabled = downloadTargets.length === 0 || Boolean(busy) || String(asset.status ?? "") === "installed";
            return (
              <div key={`${modelId}-${String(asset.backend_id ?? "")}`} style={assetRowStyle}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 650 }}>{modelId}</div>
                  <div style={{ color: "var(--muted-foreground)", fontSize: 11, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {String(asset.backend_id ?? "")} / {String(asset.model_kind ?? "")} / {detail} / {downloadTargets.length || 0} files
                  </div>
                </div>
                <TextButton aria-label={`Download ${modelId}`} disabled={disabled} onClick={() => void runModelDownload(modelId, downloadTargets)}>
                  <Download size={14} /> {statusLabel}
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

function StatusTile({ icon, label, value, detail }: { icon: ReactNode; label: string; value: string; detail: string }) {
  return (
    <div style={panelStyle}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--muted-foreground)", fontSize: 12 }}>{icon}{label}</div>
      <div style={{ marginTop: 8, fontWeight: 700, fontSize: 15 }}>{value}</div>
      <div style={{ marginTop: 4, color: "var(--muted-foreground)", fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{detail}</div>
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
