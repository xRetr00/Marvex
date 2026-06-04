import { describe, expect, it } from "vitest";
import {
  GENERIC_THINKING_LABELS,
  LISTENING_CUES,
  VOICE_THINKING_FILLERS,
  pickListeningCue,
  pickVoiceFiller,
  voiceProgressSpeech,
} from "./voiceFillers";

describe("voiceProgressSpeech", () => {
  it("swaps a generic 'Thinking' label for a playful filler the first time", () => {
    const ctx = { fillerSpoken: false, previousFiller: "" };
    const speech = voiceProgressSpeech("Thinking", ctx);
    expect(speech.skip).toBe(false);
    expect(speech.isFiller).toBe(true);
    expect(speech.text).not.toBe("Thinking");
    expect(VOICE_THINKING_FILLERS).toContain(speech.text);
  });

  it("stays silent for further generic labels once a filler was spoken", () => {
    const ctx = { fillerSpoken: true, previousFiller: "Spinning up the gears…" };
    for (const label of GENERIC_THINKING_LABELS) {
      const speech = voiceProgressSpeech(label, ctx);
      expect(speech.skip).toBe(true);
    }
  });

  it("speaks meaningful tool narration and commentary unchanged", () => {
    const ctx = { fillerSpoken: true, previousFiller: "" };
    for (const label of ["Reading config.ts", "Searching the web", "The file says testing."]) {
      const speech = voiceProgressSpeech(label, ctx);
      expect(speech.skip).toBe(false);
      expect(speech.isFiller).toBe(false);
      expect(speech.text).toBe(label);
    }
  });
});

describe("pickVoiceFiller", () => {
  it("never returns the immediately previous filler", () => {
    const previous = VOICE_THINKING_FILLERS[0];
    for (let i = 0; i < 50; i += 1) {
      expect(pickVoiceFiller(previous)).not.toBe(previous);
    }
  });
});

describe("pickListeningCue", () => {
  it("returns a known cue and avoids immediate repeats", () => {
    const previous = LISTENING_CUES[0];
    for (let i = 0; i < 50; i += 1) {
      const cue = pickListeningCue(previous);
      expect(LISTENING_CUES).toContain(cue);
      expect(cue).not.toBe(previous);
    }
  });
});
