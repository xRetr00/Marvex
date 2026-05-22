import { describe, expect, it } from "vitest";
import { displayDetail, normalizeAssistantState, shouldShowOverlay, statusLabel, waveformLevel } from "./assistantState";

describe("assistant state helpers", () => {
  it("maps assistant statuses to stable display labels", () => {
    expect(statusLabel("using_tools")).toBe("Using Tools");
    expect(statusLabel("searching_web")).toBe("Searching Web");
    expect(statusLabel("needs_approval")).toBe("Needs Approval");
  });

  it("uses only real audio level for listening and talking waveforms", () => {
    const state = normalizeAssistantState({ schema_version: "1", ts: "2026-05-22T00:00:00Z", status: "listening", audio_level: 0.73, raw_audio_persisted: false });
    expect(waveformLevel(state, 20)).toBe(0.73);
  });

  it("keeps the overlay hidden while idle", () => {
    const state = normalizeAssistantState({ schema_version: "1", ts: "2026-05-22T00:00:00Z", status: "idle", audio_level: 0, raw_audio_persisted: false });
    expect(shouldShowOverlay(state)).toBe(false);
  });

  it("falls back from empty detail to the status label", () => {
    const state = normalizeAssistantState({ schema_version: "1", ts: "2026-05-22T00:00:00Z", status: "thinking", detail: " ", audio_level: 0, raw_audio_persisted: false });
    expect(displayDetail(state)).toBe("Thinking");
  });
});
