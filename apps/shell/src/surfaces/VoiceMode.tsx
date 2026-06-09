import { useEffect, useMemo, useState } from "react";
import type { ButtonHTMLAttributes, ReactNode, CSSProperties } from "react";
import { Download, Mic, MicOff, Play, Radio, RefreshCw, SlidersHorizontal, Volume2 } from "lucide-react";
import {
  configureVoiceWorkerTtsControls,
  downloadVoiceModelGroup,
  fetchVoiceModelCatalog,
  fetchVoiceWorkerDevices,
  fetchVoiceWorkerStatus,
  reloadVoiceWorkerConfig,
  startVoiceWorker,
  stopVoiceWorker,
  switchVoiceWorkerStt,
  switchVoiceWorkerTts,
  switchVoiceWorkerVoice,
  testVoiceWorkerMic,
  testVoiceWorkerStt,
  testVoiceWorkerTts,
  type VoiceModelCatalogAsset,
  type VoiceWorkerDevices,
  type VoiceWorkerStatus
} from "@/lib/voiceControlClient";
import { loadVoiceSettings, updateVoiceSettings } from "@/lib/voiceSettings";

type ModelDownloadState = {
  state: "downloading" | "complete" | "failed";
  completed: number;
  total: number;
  error?: string;
};

export function VoiceMode() {
  const [status, setStatus] = useState<VoiceWorkerStatus | null>(null);
  const [devices, setDevices] = useState<VoiceWorkerDevices | null>(null);
  const [catalog, setCatalog] = useState<VoiceModelCatalogAsset[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [downloads, setDownloads] = useState<Record<string, ModelDownloadState>>({});
  const [message, setMessage] = useState("Loading voice worker...");

  const applyPersistedSettings = async (nextStatus: VoiceWorkerStatus, nextDevices: VoiceWorkerDevices, nextCatalog: VoiceModelCatalogAsset[]) => {
    const settings = loadVoiceSettings();
    const calls: Array<Promise<unknown>> = [];
    const sttBackendIds = new Set(nextCatalog.filter((asset) => asset.model_kind === "stt").map((asset) => asset.backend_id));
    const ttsBackendIds = new Set(nextCatalog.filter((asset) => asset.model_kind === "tts_voice").map((asset) => asset.backend_id));
    const inputDeviceIds = new Set((nextDevices.input_devices ?? []).map((device) => device.device_id));
    if (settings.sttBackendId !== nextStatus.active_stt_backend_id && sttBackendIds.has(settings.sttBackendId)) {
      calls.push(switchVoiceWorkerStt(settings.sttBackendId));
    }
    if (settings.ttsBackendId !== nextStatus.active_tts_backend_id && ttsBackendIds.has(settings.ttsBackendId)) {
      calls.push(switchVoiceWorkerTts(settings.ttsBackendId));
    }
    if (settings.voiceId !== nextStatus.active_voice_id) {
      calls.push(switchVoiceWorkerVoice(settings.voiceId));
    }
    if (
      settings.ttsSpeed !== (nextStatus.active_tts_speed ?? 1.05)
      || settings.ttsQualitySteps !== (nextStatus.active_tts_quality_steps ?? 8)
      || settings.ttsLanguage !== (nextStatus.active_tts_language ?? "en")
    ) {
      calls.push(configureVoiceWorkerTtsControls({ speed: settings.ttsSpeed, qualitySteps: settings.ttsQualitySteps, language: settings.ttsLanguage }));
    }
    const configuredInput = nextStatus.config?.audio?.input_device_id ?? nextDevices.selected_input_device_id ?? null;
    if (settings.inputDeviceId && inputDeviceIds.has(settings.inputDeviceId) && settings.inputDeviceId !== configuredInput) {
      calls.push(reloadVoiceWorkerConfig({ inputDeviceId: settings.inputDeviceId }));
    }
    if (calls.length > 0) await Promise.all(calls);
  };

  const load = async () => {
    const [nextStatus, nextCatalog, nextDevices] = await Promise.all([fetchVoiceWorkerStatus(), fetchVoiceModelCatalog(), fetchVoiceWorkerDevices()]);
    setStatus(nextStatus);
    setCatalog(nextCatalog.assets ?? []);
    setDevices(nextDevices);
    setMessage("Voice worker control is connected.");
  };

  useEffect(() => {
    let cancelled = false;
    void Promise.all([fetchVoiceWorkerStatus(), fetchVoiceModelCatalog(), fetchVoiceWorkerDevices()])
      .then(([nextStatus, nextCatalog, nextDevices]) => {
        if (cancelled) return;
        return applyPersistedSettings(nextStatus, nextDevices, nextCatalog.assets ?? [])
          .then(async () => {
            if (cancelled) return;
            const [refreshedStatus, refreshedDevices] = await Promise.all([fetchVoiceWorkerStatus(), fetchVoiceWorkerDevices()]);
            if (cancelled) return;
            setStatus(refreshedStatus);
            setCatalog(nextCatalog.assets ?? []);
            setDevices(refreshedDevices);
            setMessage("Voice worker control is connected.");
          });
      })
      .catch(() => {
        if (!cancelled) setMessage("Voice worker control is unavailable.");
      });
    return () => { cancelled = true; };
  }, []);

  const required = useMemo(() => status?.model_assets?.required ?? [], [status]);
  const requiredIds = useMemo(() => new Set(required.map((asset) => String((asset as { model_id?: unknown }).model_id ?? ""))), [required]);
  const installedIds = useMemo(
    () => new Set((status?.model_assets?.installed ?? []).map((asset) => String((asset as { model_id?: unknown }).model_id ?? ""))),
    [status],
  );
  // Optional, non-bundled models (SenseVoice multilingual STT, language-ID, etc.)
  // the user can download on demand — bundled assets and the required cards above
  // are excluded so each model appears once.
  const optionalModels = useMemo(() => {
    const seen = new Set<string>();
    const out: VoiceModelCatalogAsset[] = [];
    for (const asset of catalog) {
      if (asset.bundled || requiredIds.has(asset.model_id) || seen.has(asset.model_id)) continue;
      seen.add(asset.model_id);
      out.push(asset);
    }
    return out;
  }, [catalog, requiredIds]);
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
    return backendOptionList(catalog.filter((asset) => asset.model_kind === "stt"), status?.active_stt_backend_id ?? "moonshine-v2");
  }, [catalog, status?.active_stt_backend_id]);
  const ttsOptions = useMemo(() => {
    return optionList(catalog.filter((asset) => asset.model_kind === "tts_voice").map((asset) => asset.backend_id), status?.active_tts_backend_id ?? "supertonic-v2");
  }, [catalog, status?.active_tts_backend_id]);
  const voiceOptions = useMemo(() => {
    if ((status?.active_tts_backend_id ?? "supertonic-v2") === "supertonic-v2") {
      return optionList(SUPERTONIC_VOICES, status?.active_voice_id ?? "M1");
    }
    return optionList(catalog.filter((asset) => asset.model_kind === "tts_voice").map((asset) => asset.model_id), status?.active_voice_id ?? "M1");
  }, [catalog, status?.active_tts_backend_id, status?.active_voice_id]);
  const ttsSpeed = status?.active_tts_speed ?? 1.05;
  const ttsQualitySteps = status?.active_tts_quality_steps ?? 8;
  const inputDeviceOptions = useMemo(() => {
    const inputs = devices?.input_devices ?? [];
    return inputs.map((device) => ({ id: device.device_id, label: device.is_default_input ? `${device.label}` : device.label }));
  }, [devices]);
  const selectedInputDeviceId = useMemo(() => {
    return (
      devices?.selected_input_device_id
      ?? status?.config?.audio?.input_device_id
      ?? devices?.input_devices.find((device) => device.is_default_input)?.device_id
      ?? devices?.input_devices[0]?.device_id
      ?? ""
    );
  }, [devices, status?.config?.audio?.input_device_id]);

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

  const runMicTest = async () => {
    const label = "Test mic";
    setBusy(label);
    try {
      const nextStatus = await testVoiceWorkerMic(selectedInputDeviceId || undefined);
      await load();
      const summary = latestEventSummary(nextStatus, "mic_started");
      const rms = numberSummary(summary?.rms_level);
      const peak = numberSummary(summary?.peak_level);
      setMessage(rms !== null && peak !== null ? `Mic level RMS ${rms.toFixed(2)}, peak ${peak.toFixed(2)}.` : "Test mic requested.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : `${label} failed.`);
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
            <div style={{ marginTop: 4, color: "var(--foreground)", fontSize: 12, fontWeight: 650 }}>Voice control deck</div>
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
        <SelectField label="STT model" value={status?.active_stt_backend_id ?? "moonshine-v2"} options={sttOptions} onChange={(value) => void run("Switch STT", async () => { const result = await switchVoiceWorkerStt(value); updateVoiceSettings({ sttBackendId: value }); return result; })} />
        <SelectField label="TTS library" value={status?.active_tts_backend_id ?? "supertonic-v2"} options={ttsOptions} onChange={(value) => void run("Switch TTS", async () => { const result = await switchVoiceWorkerTts(value); updateVoiceSettings({ ttsBackendId: value }); return result; })} />
        <SelectField label="Voice" value={status?.active_voice_id ?? "M1"} options={voiceOptions} onChange={(value) => void run("Switch voice", async () => { const result = await switchVoiceWorkerVoice(value); updateVoiceSettings({ voiceId: value }); return result; })} />
        <SelectField label="Input microphone" value={selectedInputDeviceId} options={inputDeviceOptions} onChange={(value) => void run("Select input microphone", async () => { const result = await reloadVoiceWorkerConfig({ inputDeviceId: value }); updateVoiceSettings({ inputDeviceId: value }); return result; })} />
        <TtsControlField
          speed={ttsSpeed}
          qualitySteps={ttsQualitySteps}
          busy={Boolean(busy)}
          onApply={(next) => void run("Update TTS controls", async () => {
            const language = status?.active_tts_language ?? "en";
            const result = await configureVoiceWorkerTtsControls({ ...next, language });
            updateVoiceSettings({ ttsSpeed: next.speed, ttsQualitySteps: next.qualitySteps, ttsLanguage: language });
            return result;
          })}
        />
      </section>

      <section style={gridStyle}>
        <StatusTile icon={<Radio size={16} />} label="Wake word" value={String(status?.wakeword_status ?? "unknown")} detail={String(status?.wakeword_model_status?.readiness_blocker ?? status?.wakeword_model_status?.exact_blocker ?? "ready")} />
        <StatusTile icon={<Mic size={16} />} label="STT" value={String(status?.stt_backend_status?.status ?? "unknown")} detail={String(status?.stt_backend_status?.exact_blocker ?? "ready")} />
        <StatusTile icon={<Volume2 size={16} />} label="TTS" value={String(status?.tts_backend_status?.status ?? "unknown")} detail={String(status?.tts_backend_status?.exact_blocker ?? "ready")} />
      </section>

      <section style={panelStyle}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 10 }}>
          <h3 style={{ margin: 0, fontSize: 13, letterSpacing: 0, color: "var(--foreground)", fontWeight: 750 }}>Model asset cards</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <TextButton disabled={Boolean(busy)} onClick={() => void run("Test STT", testVoiceWorkerStt)}><Play size={14} /> Test STT</TextButton>
            <TextButton disabled={Boolean(busy) || !selectedInputDeviceId} onClick={() => void runMicTest()}><Mic size={14} /> Test mic</TextButton>
            <TextButton disabled={Boolean(busy)} onClick={() => void run("Test TTS", () => testVoiceWorkerTts())}><Volume2 size={14} /> Test TTS</TextButton>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {required.map((asset) => {
            const modelId = String(asset.model_id ?? "");
            const downloadTargets = catalogTargetsFor(asset, catalogByModel, catalog);
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

      <section style={panelStyle}>
        <h3 style={{ margin: "0 0 10px", fontSize: 13, color: "var(--foreground)", fontWeight: 750 }}>Optional models</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {optionalModels.map((asset) => {
            const modelId = String(asset.model_id ?? "");
            const downloadTargets = catalogByModel.get(modelId) ?? [asset];
            const downloadState = downloads[modelId];
            const installed = installedIds.has(modelId);
            const statusLabel = downloadState?.state === "downloading"
              ? `Downloading ${downloadState.completed}/${downloadState.total}`
              : downloadState?.state === "failed"
                ? "failed"
                : (downloadState?.state === "complete" || installed)
                  ? "installed"
                  : "download";
            const disabled = downloadTargets.length === 0 || Boolean(busy) || installed;
            return (
              <div key={modelId} style={assetRowStyle}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 650 }}>{modelId}</div>
                  <div style={{ color: "var(--muted-foreground)", fontSize: 11, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {String(asset.backend_id ?? "")} / {String(asset.model_kind ?? "")} / {downloadTargets.length || 0} files
                  </div>
                </div>
                <TextButton aria-label={`Download ${modelId}`} disabled={disabled} onClick={() => void runModelDownload(modelId, downloadTargets)}>
                  <Download size={14} /> {statusLabel}
                </TextButton>
              </div>
            );
          })}
          {optionalModels.length === 0 && <span style={{ color: "var(--muted-foreground)", fontSize: 12 }}>No optional models.</span>}
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

function latestEventSummary(status: VoiceWorkerStatus | null | undefined, eventType: string): Record<string, unknown> | null {
  const events = status?.recent_events;
  if (!Array.isArray(events)) return null;
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event?.event_type !== eventType) continue;
    const summary = event.summary;
    return summary && typeof summary === "object" ? summary as Record<string, unknown> : null;
  }
  return null;
}

function numberSummary(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function TtsControlField({ speed, qualitySteps, busy, onApply }: { speed: number; qualitySteps: number; busy: boolean; onApply: (next: { speed: number; qualitySteps: number }) => void }) {
  return (
    <div style={{ ...panelStyle, gap: 10, display: "flex", flexDirection: "column" }}>
      <span style={{ color: "var(--muted-foreground)", fontSize: 12, fontWeight: 650, display: "inline-flex", alignItems: "center", gap: 6 }}><SlidersHorizontal size={14} /> TTS controls</span>
      <label style={controlLabelStyle}>
        <span>Speed {speed.toFixed(2)}</span>
        <input aria-label="TTS speed" disabled={busy} type="range" min={0.7} max={2} step={0.05} value={speed} onChange={(event) => onApply({ speed: Number(event.currentTarget.value), qualitySteps })} />
      </label>
      <label style={controlLabelStyle}>
        <span>Quality {qualitySteps}</span>
        <input aria-label="TTS quality" disabled={busy} type="range" min={5} max={12} step={1} value={qualitySteps} onChange={(event) => onApply({ speed, qualitySteps: Number(event.currentTarget.value) })} />
      </label>
    </div>
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

function backendOptionList(assets: VoiceModelCatalogAsset[], active: string): Array<{ id: string; label: string }> {
  const options = new Map<string, string>();
  if (active) options.set(active, active);
  for (const asset of assets) {
    const backendId = String(asset.backend_id ?? "").trim();
    if (!backendId || options.has(backendId)) continue;
    options.set(backendId, String(asset.model_id ?? backendId));
  }
  return [...options].map(([id, label]) => ({ id, label }));
}

const SUPERTONIC_VOICES = ["M1", "M2", "M3", "M4", "M5", "F1", "F2", "F3", "F4", "F5"];

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
  background: "linear-gradient(180deg, color-mix(in srgb, var(--card) 88%, transparent), color-mix(in srgb, var(--secondary) 48%, transparent))",
  border: "1px solid color-mix(in srgb, var(--foreground) 10%, transparent)",
  borderRadius: 8,
  padding: 14,
  boxShadow: "var(--shadow-card)",
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

const controlLabelStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "72px minmax(0, 1fr)",
  alignItems: "center",
  gap: 10,
  fontSize: 12,
  color: "var(--foreground)",
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
  boxShadow: "var(--shadow-card)",
};
