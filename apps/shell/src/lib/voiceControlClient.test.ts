import { describe, expect, it, vi } from "vitest";
import { controlRequest } from "./shellCommands";
import { configureVoiceWorkerTtsControls, downloadVoiceModel, downloadVoiceModelGroup, fetchVoiceModelCatalog, switchVoiceWorkerStt, switchVoiceWorkerTts, switchVoiceWorkerVoice, testVoiceWorkerTts } from "./voiceControlClient";

vi.mock("./shellCommands", () => ({
  controlRequest: vi.fn(async () => ({ ok: true }))
}));

const mockedControlRequest = vi.mocked(controlRequest);

describe("voice control client", () => {
  it("calls worker endpoints for selectors and explicit downloads", async () => {
    await fetchVoiceModelCatalog();
    await switchVoiceWorkerStt("moonshine-v2");
    await switchVoiceWorkerTts("supertonic-v2");
    await switchVoiceWorkerVoice("M1");
    await configureVoiceWorkerTtsControls({ speed: 1.1, qualitySteps: 10, language: "en" });
    await testVoiceWorkerTts("Voice test.", { speed: 1.1, qualitySteps: 10, language: "en" });
    await downloadVoiceModel({
      model_id: "hey-marvex",
      backend_id: "sherpa-onnx-kws",
      model_kind: "wakeword",
      source_uri: "https://models.example.test/hey-marvex.tar.gz",
      relative_path: "wakeword/hey-marvex",
      extract: true,
      explicit_user_triggered: true
    });

    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/models/catalog", "GET");
    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/stt/switch", "POST", { backend_id: "moonshine-v2" });
    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/tts/switch", "POST", { backend_id: "supertonic-v2" });
    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/voice/switch", "POST", { voice_id: "M1" });
    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/tts/configure", "POST", { speed: 1.1, quality_steps: 10, language: "en" });
    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/test-tts", "POST", { text: "Voice test.", speed: 1.1, quality_steps: 10, language: "en" });
    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/models/download", "POST", {
      model_id: "hey-marvex",
      backend_id: "sherpa-onnx-kws",
      model_kind: "wakeword",
      source_uri: "https://models.example.test/hey-marvex.tar.gz",
      relative_path: "wakeword/hey-marvex",
      extract: true,
      explicit_user_triggered: true
    });
  });

  it("downloads every catalog asset in a model group and reports progress", async () => {
    const progress: Array<{ completed: number; total: number; modelId: string }> = [];

    await downloadVoiceModelGroup(
      [
        {
          model_id: "moonshine-v2",
          backend_id: "moonshine-v2",
          model_kind: "stt",
          source_uri: "https://models.example.test/encoder.ort",
          relative_path: "stt/moonshine-v2/encoder.ort",
          install_relative_path: "stt/moonshine-v2",
          explicit_user_triggered: true
        },
        {
          model_id: "moonshine-v2",
          backend_id: "moonshine-v2",
          model_kind: "stt",
          source_uri: "https://models.example.test/tokenizer.bin",
          relative_path: "stt/moonshine-v2/tokenizer.bin",
          install_relative_path: "stt/moonshine-v2",
          explicit_user_triggered: true
        }
      ],
      (event) => progress.push({ completed: event.completed, total: event.total, modelId: event.asset.model_id })
    );

    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/models/download", "POST", expect.objectContaining({ relative_path: "stt/moonshine-v2/encoder.ort" }));
    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/models/download", "POST", expect.objectContaining({ relative_path: "stt/moonshine-v2/tokenizer.bin" }));
    expect(progress).toEqual([
      { completed: 1, total: 2, modelId: "moonshine-v2" },
      { completed: 2, total: 2, modelId: "moonshine-v2" }
    ]);
  });
});
