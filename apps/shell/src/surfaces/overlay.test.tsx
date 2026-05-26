import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { toOverlayWindowSize, WaveformCanvas } from "./overlay";

vi.mock("../lib/tauriBridge", () => ({ listen: vi.fn(async () => vi.fn()) }));
vi.mock("../lib/shellCommands", () => ({ setOverlaySize: vi.fn(), showChat: vi.fn() }));
vi.mock("../lib/controlPlaneClient", () => ({
  fetchPendingApprovals: vi.fn(async () => []),
  decideApproval: vi.fn(),
}));

describe("WaveformCanvas", () => {
  it("renders an accessible waveform canvas bound to assistant state", () => {
    render(<WaveformCanvas state={{ schema_version: "1", ts: "2026-05-22T00:00:00Z", status: "talking", detail: null, audio_level: 0.6, session_ref: null, trace_id: null, raw_audio_persisted: false }} />);
    expect(screen.getByLabelText("Assistant audio level waveform")).toBeInTheDocument();
  });
});

describe("overlay sizing", () => {
  it("keeps the native window exactly on the rendered island bounds", () => {
    expect(toOverlayWindowSize({ width: 128.2, height: 42.1 })).toEqual({ width: 128, height: 42 });
  });
});
