import { controlRequest } from "./shellCommands";

export type VoiceModelKind = "stt" | "tts_voice" | "wakeword" | "vad" | "langid";

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
  /** Bundled assets ship in the installer; they're selectable but not downloadable. */
  bundled?: boolean;
  explicit_user_triggered: true;
  raw_payload_persisted?: false;
};

export type VoiceWorkerStatus = {
  schema_version: string;
  lifecycle_state: string;
  process_started: boolean;
  config?: {
    audio?: {
      input_device_id?: string | null;
      output_device_id?: string | null;
      sample_rate?: number;
      channel_count?: number;
      frame_duration_ms?: number;
    };
  };
  active_stt_backend_id: string;
  active_tts_backend_id: string;
  active_voice_id: string;
  active_tts_speed?: number;
  active_tts_quality_steps?: number;
  active_tts_language?: string;
  wakeword_status: string;
  effective_wakeword_backend_id?: string;
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

export type VoiceAudioDevice = {
  device_id: string;
  label: string;
  host_api?: string;
  max_input_channels?: number;
  max_output_channels?: number;
  default_sample_rate?: number;
  is_input?: boolean;
  is_output?: boolean;
  is_default_input?: boolean;
  is_default_output?: boolean;
};

export type VoiceWorkerDevices = {
  schema_version: string;
  input_devices: VoiceAudioDevice[];
  output_devices: VoiceAudioDevice[];
  selected_input_device_id?: string | null;
  selected_output_device_id?: string | null;
  raw_audio_persisted?: false;
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

export function fetchVoiceWorkerDevices(): Promise<VoiceWorkerDevices> {
  return controlRequest("/voice/worker/devices", "GET") as Promise<VoiceWorkerDevices>;
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

export function testVoiceWorkerTts(text = "Voice test.", options?: { speed?: number; qualitySteps?: number; language?: string }): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/test-tts", "POST", {
    text,
    speed: options?.speed,
    quality_steps: options?.qualitySteps,
    language: options?.language
  }) as Promise<VoiceWorkerStatus>;
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

export function configureVoiceWorkerTtsControls(options: { speed: number; qualitySteps: number; language?: string }): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/tts/configure", "POST", {
    speed: options.speed,
    quality_steps: options.qualitySteps,
    language: options.language
  }) as Promise<VoiceWorkerStatus>;
}

export function reloadVoiceWorkerConfig(options: { inputDeviceId?: string | null; outputDeviceId?: string | null }): Promise<VoiceWorkerStatus> {
  const body: Record<string, unknown> = {};
  if ("inputDeviceId" in options) body.input_device_id = options.inputDeviceId;
  if ("outputDeviceId" in options) body.output_device_id = options.outputDeviceId;
  return controlRequest("/voice/worker/reload-config", "POST", body) as Promise<VoiceWorkerStatus>;
}

export function testVoiceWorkerMic(deviceId?: string | null): Promise<VoiceWorkerStatus> {
  return controlRequest("/voice/worker/test-mic", "POST", { device_id: deviceId ?? undefined }) as Promise<VoiceWorkerStatus>;
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
 * Extract the most recent recognized transcript from a worker status snapshot.
 * The worker emits normalized_transcript_text on TRANSCRIPTION_COMPLETED after
 * wake or push-to-talk capture; the shell picks it up and drives the turn.
 */
export function transcriptFromStatus(status: VoiceWorkerStatus | null | undefined): { text: string; eventId: string } | null {
  const events = (status as { recent_events?: Array<Record<string, unknown>> } | null | undefined)?.recent_events;
  if (!Array.isArray(events)) return null;
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (!event || typeof event !== "object") continue;
    if ((event as { event_type?: unknown }).event_type !== "transcription_completed") continue;
    const summary = (event as { summary?: Record<string, unknown> }).summary;
    const normalized = summary && typeof summary.normalized_transcript_text === "string" ? summary.normalized_transcript_text : undefined;
    const legacy = summary && typeof summary.transcript_text === "string" ? summary.transcript_text : undefined;
    const text = (normalized ?? legacy ?? "").trim();
    if (!text) return null;
    const eventId = String((event as { event_id?: unknown }).event_id ?? "");
    return { text, eventId };
  }
  return null;
}

/**
 * Surface the most recent *rejected* capture and its reason (e.g. the language
 * gate's `non_english_ignored`) so the shell can show a brief one-time notice
 * when a turn was dropped on purpose and nothing else happens.
 */
export function voiceRejectionFromStatus(status: VoiceWorkerStatus | null | undefined): { reason: string; eventId: string } | null {
  const events = (status as { recent_events?: Array<Record<string, unknown>> } | null | undefined)?.recent_events;
  if (!Array.isArray(events)) return null;
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (!event || typeof event !== "object") continue;
    if ((event as { event_type?: unknown }).event_type !== "transcription_completed") continue;
    const summary = (event as { summary?: Record<string, unknown> }).summary;
    const reason = summary && typeof summary.transcript_rejected_reason === "string" ? summary.transcript_rejected_reason : "";
    if (!reason) return null;
    return { reason, eventId: String((event as { event_id?: unknown }).event_id ?? "") };
  }
  return null;
}

/**
 * Latest live partial transcript while the user is still speaking (Moonshine
 * streaming). Returns null once the turn completes — a `transcription_completed`
 * seen before any partial means there's no active partial to show.
 */
export function partialTranscriptFromStatus(status: VoiceWorkerStatus | null | undefined): string | null {
  const events = (status as { recent_events?: Array<Record<string, unknown>> } | null | undefined)?.recent_events;
  if (!Array.isArray(events)) return null;
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (!event || typeof event !== "object") continue;
    const type = (event as { event_type?: unknown }).event_type;
    if (type === "transcription_completed") return null;
    if (type === "transcription_partial") {
      const summary = (event as { summary?: Record<string, unknown> }).summary;
      const text = summary && typeof summary.partial_transcript_text === "string" ? summary.partial_transcript_text.trim() : "";
      return text || null;
    }
  }
  return null;
}

export function wakeDetectionFromStatus(status: VoiceWorkerStatus | null | undefined): { eventId: string; confidence?: number } | null {
  const events = (status as { recent_events?: Array<Record<string, unknown>> } | null | undefined)?.recent_events;
  if (!Array.isArray(events)) return null;
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (!event || typeof event !== "object") continue;
    if ((event as { event_type?: unknown }).event_type !== "wakeword_detected") continue;
    const summary = (event as { summary?: Record<string, unknown> }).summary;
    const rawConfidence = summary?.confidence;
    const confidence = typeof rawConfidence === "number" ? rawConfidence : undefined;
    return { eventId: String((event as { event_id?: unknown }).event_id ?? ""), confidence };
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
