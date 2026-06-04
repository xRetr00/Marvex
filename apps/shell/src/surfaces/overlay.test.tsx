import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OverlaySurface, toOverlayWindowSize } from "./overlay";
import { ISLAND_GEOMETRY } from "@/components/dynamic-island/geometry.generated";
import { submitChatTurnStream } from "../lib/shellCommands";
import { fetchVoiceWorkerStatus, speakVoiceWorker, transcriptFromStatus } from "../lib/voiceControlClient";
import { getPersistedMode } from "../lib/modeStore";

vi.mock("../lib/tauriBridge", () => ({ listen: vi.fn(async () => vi.fn()) }));
vi.mock("../lib/backendStatus", () => ({
  useBackendStatus: () => ({ ready: true, phase: "ready", launched: true, services: {}, wakeword: "running" }),
}));
vi.mock("../lib/shellCommands", () => ({
  createChatSession: vi.fn(async () => ({ session: { session_ref: { ref_id: "overlay-session" }, title: "Overlay voice", updated_at_unix_ms: 0 } })),
  listChatSessions: vi.fn(async () => ({ sessions: [] })),
  setOverlaySize: vi.fn(),
  showChat: vi.fn(),
  submitChatTurnStream: vi.fn(async () => ({ assistant_final_response: { text: "Done." } })),
}));
vi.mock("../lib/controlPlaneClient", () => ({
  fetchPendingApprovals: vi.fn(async () => []),
}));
vi.mock("../lib/voiceControlClient", () => ({
  fetchVoiceWorkerStatus: vi.fn(async () => ({ recent_events: [] })),
  speakVoiceWorker: vi.fn(async () => ({ recent_events: [] })),
  transcriptFromStatus: vi.fn(() => null),
}));
vi.mock("../lib/modeStore", () => ({
  getPersistedMode: vi.fn(() => "overlay"),
  persistMode: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("overlay sizing", () => {
  it("adds the geometry shadow padding so the native rounded window does not clip the pill", () => {
    const pad = ISLAND_GEOMETRY.shadowPadding;
    expect(toOverlayWindowSize({ width: 128.2, height: 42.1 })).toEqual({
      width: 128 + pad * 2,
      height: 42 + pad * 2,
    });
  });
});

describe("OverlaySurface", () => {
  it("shows wake-word status in overlay mode", () => {
    render(<OverlaySurface />);
    expect(screen.getByText("Hey Marvex on")).toBeInTheDocument();
  });

  it("routes wake transcripts through the overlay voice turn bridge", async () => {
    vi.mocked(transcriptFromStatus).mockReturnValueOnce({ text: "wake transcript", eventId: "wake-event-1" }).mockReturnValue(null);

    render(<OverlaySurface />);

    await waitFor(() => expect(fetchVoiceWorkerStatus).toHaveBeenCalled(), { timeout: 2500 });
    await waitFor(() => expect(submitChatTurnStream).toHaveBeenCalledWith(
      "wake transcript",
      { session_id: "overlay-session" },
      undefined,
      expect.objectContaining({
        onDelta: expect.any(Function),
        onStatus: expect.any(Function),
        onTool: expect.any(Function),
      }),
    ), { timeout: 2500 });
    expect(speakVoiceWorker).toHaveBeenCalledWith("Done.", { bargeIn: true });
  });

  it("does not consume wake transcripts while chat mode owns voice", async () => {
    vi.mocked(getPersistedMode).mockReturnValue("chat");
    vi.mocked(transcriptFromStatus).mockReturnValue({ text: "wake transcript", eventId: "wake-event-chat-mode" });

    render(<OverlaySurface />);

    await new Promise((resolve) => setTimeout(resolve, 1700));
    expect(fetchVoiceWorkerStatus).not.toHaveBeenCalled();
    expect(submitChatTurnStream).not.toHaveBeenCalled();
  });
});
