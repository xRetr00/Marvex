import { controlRequest } from "./shellCommands";

export type VoiceModelKind = "stt" | "tts_voice" | "wakeword" | "vad";

export type VoiceModelCatalogAsset = {
  schema_version?: string;
  model_id: string;
  backend_id: string;
  model_kind: VoiceModelKind;
  source_uri: string;
  relative_path: string;
  install_relative_path?: string | null;
  extract?: boolean;
  checksum_sha256?: string | null;
  required?: boolean;
  explicit_user_triggered: true;
  raw_payload_persisted?: false;
};

export type VoiceWorkerStatus = {
  schema_version: string;
  lifecycle_state: string;
  process_started: boolean;
  active_stt_backend_id: string;
  active_tts_backend_id: string;
  active_voice_id: string;
  wakeword_status: string;
  model_assets?: {
    installed?: Array<Record<string, unknown>>;
    installed_count?: number;
    required?: Array<Record<string, unknown>>;
    required_ready_count?: number;
    required_blocked_count?: number;
  };
  stt_backend_status?: Record<string, unknown>;
  tts_backend_status?: Record<string, unknown>;
  wakeword_model_status?: Record<string, unknown>;
  recent_events?: Array<Record<string, unknown>>;
};

export type VoiceModelCatalog = {
  schema_version: string;
  assets: VoiceModelCatalogAsset[];
  raw_payload_persisted: false;
};

export type VoiceModelDownloadProgress = {
  asset: VoiceModelCatalogAsset;
  completed: number;
  total: number;
};

export function fetchVoiceWorkerStatus(): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker", "GET") as Promise<VoiceWorkerStatus>;
}

export function fetchVoiceWorkerAssets(): Promise<VoiceWorkerStatus["model_assets"]> {
  return controlRequest("/voice/worker/assets", "GET") as Promise<VoiceWorkerStatus["model_assets"]>;
}

export function fetchVoiceModelCatalog(): Promise<VoiceModelCatalog> {
  return controlRequest("/voice/worker/models/catalog", "GET") as Promise<VoiceModelCatalog>;
}

export function startVoiceWorker(): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/start", "POST", {}) as Promise<VoiceWorkerStatus>;
}

export function stopVoiceWorker(): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/stop", "POST", {}) as Promise<VoiceWorkerStatus>;
}

export function testVoiceWorkerStt(): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/test-stt", "POST", {}) as Promise<VoiceWorkerStatus>;
}

export function testVoiceWorkerTts(text = "Voice test."): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/test-tts", "POST", { text }) as Promise<VoiceWorkerStatus>;
}

export function switchVoiceWorkerStt(backendId: string): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/stt/switch", "POST", { backend_id: backendId }) as Promise<VoiceWorkerStatus>;
}

export function switchVoiceWorkerTts(backendId: string): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/tts/switch", "POST", { backend_id: backendId }) as Promise<VoiceWorkerStatus>;
}

export function switchVoiceWorkerVoice(voiceId: string): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/voice/switch", "POST", { voice_id: voiceId }) as Promise<VoiceWorkerStatus>;
}

/** Speak an assistant reply through the worker's active TTS (closes the voice loop). */
export function speakVoiceWorker(text: string, options?: { bargeIn?: boolean }): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/speak", "POST", { text, barge_in: options?.bargeIn ?? false }) as Promise<VoiceWorkerStatus>;
}

/**
 * Capture one follow-up utterance on demand (no wake word required). Used after
 * the assistant finishes speaking to keep a hands-free multi-turn conversation
 * going; if the user stays silent the worker bails and the loop returns to
 * wake-word listening.
 */
export function listenVoiceWorker(): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/listen", "POST", {}) as Promise<VoiceWorkerStatus>;
}

/**
 * Record one "Hey Marvex" reference sample for the local-wake backend (in-app
 * enrollment). Call 4-6 times; each VAD-endpoints one utterance and saves a
 * reference WAV. The worker returns the saved path + running reference count in
 * the latest event summary.
 */
export function recordWakeReference(phrase = "Hey Marvex"): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/record-wake-reference", "POST", { phrase }) as Promise<VoiceWorkerStatus>;
}

/**
 * Extract the most recent recognized transcript from a worker status snapshot.
 * The worker emits transcript_text on a TRANSCRIPTION_COMPLETED event after a
 * wake-word capture; the shell polls status, picks it up, and drives the turn.
 */
export function transcriptFromStatus(status: VoiceWorkerStatus | null | undefined): { text: string; eventId: string } | null {
  const events = (status as { recent_events?: Array<Record<string, unknown>> } | null | undefined)?.recent_events;
  if (!Array.isArray(events)) return null;
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (!event || typeof event !== "object") continue;
    if ((event as { event_type?: unknown }).event_type !== "transcription_completed") continue;
    const summary = (event as { summary?: Record<string, unknown> }).summary;
    const text = summary && typeof summary.transcript_text === "string" ? summary.transcript_text.trim() : "";
    if (!text) return null;
    const eventId = String((event as { event_id?: unknown }).event_id ?? "");
    return { text, eventId };
  }
  return null;
}

export function downloadVoiceModel(asset: VoiceModelCatalogAsset): Promise<unknown> {
  const body: Record<string, unknown> = {
    model_id: asset.model_id,
    backend_id: asset.backend_id,
    model_kind: asset.model_kind,
    source_uri: asset.source_uri,
    relative_path: asset.relative_path,
    extract: Boolean(asset.extract),
    explicit_user_triggered: true
  };
  if (asset.install_relative_path) body.install_relative_path = asset.install_relative_path;
  if (asset.checksum_sha256) body.checksum_sha256 = asset.checksum_sha256;
  return controlRequest("/voice/worker/models/download", "POST", body);
}

export async function downloadVoiceModelGroup(
  assets: VoiceModelCatalogAsset[],
  onProgress?: (event: VoiceModelDownloadProgress) => void
): Promise<unknown[]> {
  const results: unknown[] = [];
  const total = assets.length;
  for (const asset of assets) {
    const result = await downloadVoiceModel(asset);
    results.push(result);
    onProgress?.({ asset, completed: results.length, total });
  }
  return results;
}
