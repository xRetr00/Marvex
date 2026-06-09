export type VoiceSettings = {
  sttBackendId: string;
  ttsBackendId: string;
  voiceId: string;
  ttsSpeed: number;
  ttsQualitySteps: number;
  ttsLanguage: string;
  inputDeviceId: string | null;
  outputDeviceId: string | null;
};

const STORAGE_KEY = "marvex.voice.settings.v1";

export const defaultVoiceSettings: VoiceSettings = {
  sttBackendId: "moonshine-v2",
  ttsBackendId: "supertonic-v2",
  voiceId: "M1",
  ttsSpeed: 1.05,
  ttsQualitySteps: 8,
  ttsLanguage: "en",
  inputDeviceId: null,
  outputDeviceId: null,
};

export function loadVoiceSettings(): VoiceSettings {
  if (typeof localStorage === "undefined") return { ...defaultVoiceSettings };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...defaultVoiceSettings };
    return normalizeVoiceSettings(JSON.parse(raw));
  } catch {
    return { ...defaultVoiceSettings };
  }
}

export function saveVoiceSettings(settings: VoiceSettings): VoiceSettings {
  const normalized = normalizeVoiceSettings(settings);
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  }
  return normalized;
}

export function updateVoiceSettings(patch: Partial<VoiceSettings>): VoiceSettings {
  return saveVoiceSettings({ ...loadVoiceSettings(), ...patch });
}

function normalizeVoiceSettings(value: unknown): VoiceSettings {
  const raw = value && typeof value === "object" ? value as Partial<VoiceSettings> : {};
  return {
    sttBackendId: nonEmptyString(raw.sttBackendId, defaultVoiceSettings.sttBackendId),
    ttsBackendId: nonEmptyString(raw.ttsBackendId, defaultVoiceSettings.ttsBackendId),
    voiceId: nonEmptyString(raw.voiceId, defaultVoiceSettings.voiceId),
    ttsSpeed: boundedNumber(raw.ttsSpeed, defaultVoiceSettings.ttsSpeed, 0.7, 2.0),
    ttsQualitySteps: Math.round(boundedNumber(raw.ttsQualitySteps, defaultVoiceSettings.ttsQualitySteps, 5, 12)),
    ttsLanguage: nonEmptyString(raw.ttsLanguage, defaultVoiceSettings.ttsLanguage),
    inputDeviceId: nullableString(raw.inputDeviceId),
    outputDeviceId: nullableString(raw.outputDeviceId),
  };
}

function nonEmptyString(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function boundedNumber(value: unknown, fallback: number, min: number, max: number): number {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.max(min, Math.min(max, number));
}
