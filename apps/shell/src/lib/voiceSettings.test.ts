import { afterEach, describe, expect, it } from "vitest";
import { defaultVoiceSettings, loadVoiceSettings, saveVoiceSettings } from "./voiceSettings";

afterEach(() => {
  localStorage.clear();
});

describe("voiceSettings", () => {
  it("defaults to the bundled voice stack", () => {
    const settings = loadVoiceSettings();

    expect(settings.sttBackendId).toBe("moonshine-v2");
    expect(settings.ttsBackendId).toBe("supertonic-v2");
    expect(settings.voiceId).toBe("M1");
    expect(settings.ttsSpeed).toBe(1.05);
    expect(settings.ttsQualitySteps).toBe(8);
    expect(settings.inputDeviceId).toBeNull();
  });

  it("persists voice, TTS controls, STT, and microphone choices", () => {
    saveVoiceSettings({
      ...defaultVoiceSettings,
      sttBackendId: "sensevoice-small",
      voiceId: "F2",
      ttsSpeed: 1.25,
      ttsQualitySteps: 10,
      inputDeviceId: "19",
    });

    const settings = loadVoiceSettings();

    expect(settings.sttBackendId).toBe("sensevoice-small");
    expect(settings.voiceId).toBe("F2");
    expect(settings.ttsSpeed).toBe(1.25);
    expect(settings.ttsQualitySteps).toBe(10);
    expect(settings.inputDeviceId).toBe("19");
    expect(settings.ttsBackendId).toBe(defaultVoiceSettings.ttsBackendId);
  });
});
