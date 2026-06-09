import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VoiceMode } from "./VoiceMode";
import * as voiceClient from "@/lib/voiceControlClient";

const status = {
  schema_version: "1",
  lifecycle_state: "stopped",
  process_started: false,
  active_stt_backend_id: "moonshine-v2",
  active_tts_backend_id: "supertonic-v2",
  active_voice_id: "M1",
  active_tts_speed: 1.05,
  active_tts_quality_steps: 8,
  active_tts_language: "en",
  wakeword_status: "enabled",
  model_assets: {
    installed: [],
    installed_count: 0,
    required: [
      { model_id: "moonshine-v2", backend_id: "moonshine-v2", model_kind: "stt", status: "not_installed", exact_blocker: "model_path_not_found_under_voice_asset_root" },
      { model_id: "supertonic-v2", backend_id: "supertonic-v2", model_kind: "tts_voice", status: "not_installed", exact_blocker: "model_path_not_found_under_voice_asset_root" }
    ],
    required_ready_count: 0,
    required_blocked_count: 2
  },
  stt_backend_status: { status: "not_ready", exact_blocker: "model_asset_missing_manual_install_required" },
  tts_backend_status: { status: "not_ready", exact_blocker: "model_asset_missing_manual_install_required" },
  wakeword_model_status: { readiness_status: "not_ready", readiness_blocker: "model_asset_missing_manual_install_required" }
};

const catalog = {
  schema_version: "1",
  assets: [
    {
      model_id: "moonshine-v2",
      backend_id: "moonshine-v2",
      model_kind: "stt",
      relative_path: "stt/moonshine/encoder.ort",
      source_uri: "https://download.moonshine.ai/model/medium-streaming-en/quantized/encoder.ort",
      extract: false,
      required: true,
      explicit_user_triggered: true
    },
    {
      model_id: "moonshine-v2",
      backend_id: "moonshine-v2",
      model_kind: "stt",
      relative_path: "stt/moonshine/tokenizer.bin",
      install_relative_path: "stt/moonshine",
      source_uri: "https://download.moonshine.ai/model/medium-streaming-en/quantized/tokenizer.bin",
      extract: false,
      required: true,
      explicit_user_triggered: true
    },
    {
      model_id: "whisper-large-v3",
      backend_id: "whisper.cpp",
      model_kind: "stt",
      relative_path: "stt/whisper-large-v3/model.bin",
      source_uri: "https://models.example.test/whisper-large-v3/model.bin",
      extract: false,
      required: false,
      explicit_user_triggered: true
    },
    {
      model_id: "supertonic-v2",
      backend_id: "supertonic-v2",
      model_kind: "tts_voice",
      relative_path: "tts/supertonic-v2/config.json",
      source_uri: "https://huggingface.co/Supertone/supertonic-2/resolve/main/config.json",
      extract: false,
      required: true,
      explicit_user_triggered: true
    },
    {
      model_id: "piper-en-us",
      backend_id: "piper-tts",
      model_kind: "tts_voice",
      relative_path: "tts/piper-en-us/model.onnx",
      source_uri: "https://models.example.test/piper-en-us/model.onnx",
      extract: false,
      required: false,
      explicit_user_triggered: true
    }
  ],
  raw_payload_persisted: false
};

vi.mock("@/lib/voiceControlClient", () => ({
  fetchVoiceWorkerStatus: vi.fn(async () => status),
  fetchVoiceModelCatalog: vi.fn(async () => catalog),
  startVoiceWorker: vi.fn(async () => status),
  stopVoiceWorker: vi.fn(async () => status),
  testVoiceWorkerStt: vi.fn(async () => status),
  testVoiceWorkerTts: vi.fn(async () => status),
  switchVoiceWorkerStt: vi.fn(async () => status),
  switchVoiceWorkerTts: vi.fn(async () => status),
  switchVoiceWorkerVoice: vi.fn(async () => status),
  configureVoiceWorkerTtsControls: vi.fn(async () => status),
  downloadVoiceModel: vi.fn(async () => ({ status: "installed" })),
  downloadVoiceModelGroup: vi.fn(async (_assets, onProgress) => {
    onProgress?.({ asset: catalog.assets[0], completed: 1, total: 2 });
    onProgress?.({ asset: catalog.assets[1], completed: 2, total: 2 });
    return [{ status: "installed" }, { status: "installed" }];
  })
}));

describe("VoiceMode", () => {
  afterEach(() => cleanup());

  it("shows STT/TTS selectors, model assets, and explicit backend actions", async () => {
    const user = userEvent.setup();
    render(<VoiceMode />);

    expect(await screen.findByRole("heading", { name: "Voice Mode" })).toBeInTheDocument();
    expect(await screen.findByText("Voice control deck")).toBeInTheDocument();
    expect(await screen.findByText("Model asset cards")).toBeInTheDocument();
    expect(screen.getByLabelText("STT model")).toHaveValue("moonshine-v2");
    expect(screen.getByLabelText("TTS library")).toHaveValue("supertonic-v2");
    expect(screen.getByLabelText("Voice")).toHaveValue("M1");
    expect(screen.getByLabelText("TTS speed")).toHaveValue("1.05");
    expect(screen.getByLabelText("TTS quality")).toHaveValue("8");
    expect(screen.getByRole("option", { name: "whisper-large-v3" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "piper-tts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download piper-en-us" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "F3" })).toBeInTheDocument();
    expect(screen.getAllByText("moonshine-v2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("supertonic-v2").length).toBeGreaterThan(0);

    await user.selectOptions(screen.getByLabelText("TTS library"), "piper-tts");
    await user.selectOptions(screen.getByLabelText("Voice"), "F3");
    await user.click(screen.getByLabelText("TTS quality"));
    await user.click(screen.getByRole("button", { name: "Download moonshine-v2" }));

    await waitFor(() => expect(voiceClient.switchVoiceWorkerTts).toHaveBeenCalledWith("piper-tts"));
    await waitFor(() => expect(voiceClient.switchVoiceWorkerVoice).toHaveBeenCalledWith("F3"));
    await waitFor(() => expect(voiceClient.downloadVoiceModelGroup).toHaveBeenCalledWith(catalog.assets.filter((asset) => asset.model_id === "moonshine-v2"), expect.any(Function)));
    expect(screen.getByText("Download moonshine-v2 requested.")).toBeInTheDocument();
  });

  it("keeps conversation controls out of the Voice Mode diagnostics page", async () => {
    render(<VoiceMode />);
    expect(await screen.findByRole("heading", { name: "Voice Mode" })).toBeInTheDocument();
    expect(screen.queryByText("Conversation session")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Wake word voice session" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Hands-free voice session" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Hold to talk" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop voice session" })).not.toBeInTheDocument();
  });
});
