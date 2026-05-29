import { describe, expect, it } from "vitest";
import { transcriptFromStatus } from "./voiceControlClient";

describe("transcriptFromStatus", () => {
  it("returns the latest transcription_completed transcript_text", () => {
    const status = {
      recent_events: [
        { event_id: "e1", event_type: "wakeword_detected", summary: {} },
        { event_id: "e2", event_type: "transcription_completed", summary: { transcript_text: "what is open source" } },
      ],
    } as never;
    expect(transcriptFromStatus(status)).toEqual({ text: "what is open source", eventId: "e2" });
  });

  it("picks the MOST RECENT transcript when several exist", () => {
    const status = {
      recent_events: [
        { event_id: "e1", event_type: "transcription_completed", summary: { transcript_text: "first" } },
        { event_id: "e2", event_type: "transcription_completed", summary: { transcript_text: "second" } },
      ],
    } as never;
    expect(transcriptFromStatus(status)?.text).toBe("second");
  });

  it("returns null when no transcription event is present", () => {
    const status = { recent_events: [{ event_id: "e1", event_type: "mic_started", summary: {} }] } as never;
    expect(transcriptFromStatus(status)).toBeNull();
  });

  it("returns null when transcript text is empty/whitespace", () => {
    const status = {
      recent_events: [{ event_id: "e1", event_type: "transcription_completed", summary: { transcript_text: "   " } }],
    } as never;
    expect(transcriptFromStatus(status)).toBeNull();
  });

  it("handles missing/!array recent_events safely", () => {
    expect(transcriptFromStatus(null)).toBeNull();
    expect(transcriptFromStatus(undefined)).toBeNull();
    expect(transcriptFromStatus({} as never)).toBeNull();
  });
});
