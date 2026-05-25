import { describe, expect, it, vi } from "vitest";
import { controlRequest } from "./shellCommands";
import { downloadVoiceModel, fetchVoiceModelCatalog, switchVoiceWorkerStt, switchVoiceWorkerTts, switchVoiceWorkerVoice } from "./voiceControlClient";

vi.mock("./shellCommands", () => ({
  controlRequest: vi.fn(async () => ({ ok: true }))
}));

const mockedControlRequest = vi.mocked(controlRequest);

describe("voice control client", () => {
  it("calls worker endpoints for selectors and explicit downloads", async () => {
    await fetchVoiceModelCatalog();
    await switchVoiceWorkerStt("moonshine-v2");
    await switchVoiceWorkerTts("kokoro-onnx");
    await switchVoiceWorkerVoice("af_heart");
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
    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/tts/switch", "POST", { backend_id: "kokoro-onnx" });
    expect(mockedControlRequest).toHaveBeenCalledWith("/voice/worker/voice/switch", "POST", { voice_id: "af_heart" });
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
});
