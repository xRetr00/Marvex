import { describe, expect, it, vi } from "vitest";
import { runVoiceTurnWithSpeech } from "./voiceTurnSpeech";

describe("runVoiceTurnWithSpeech", () => {
  it("speaks a filler when the turn takes longer than the filler delay", async () => {
    vi.useFakeTimers();
    const speak = vi.fn(async () => undefined);
    const runTurn = vi.fn(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 50));
      return { speechText: "Final reply." };
    });

    const promise = runVoiceTurnWithSpeech({
      runTurn,
      speechText: (result) => result.speechText,
      speak,
      fillerDelayMs: 10,
      selectFiller: () => "One moment.",
    });

    await vi.advanceTimersByTimeAsync(10);
    expect(speak).toHaveBeenCalledWith("One moment.", { bargeIn: false });
    await vi.advanceTimersByTimeAsync(50);
    await promise;

    expect(speak).toHaveBeenLastCalledWith("Final reply.", { bargeIn: true });
    vi.useRealTimers();
  });

  it("does not speak filler or final audio after the voice session is cancelled", async () => {
    vi.useFakeTimers();
    let active = true;
    const speak = vi.fn(async () => undefined);
    const promise = runVoiceTurnWithSpeech({
      runTurn: async () => {
        await new Promise((resolve) => window.setTimeout(resolve, 50));
        return { speechText: "Final reply." };
      },
      speechText: (result) => result.speechText,
      speak,
      shouldSpeak: () => active,
      fillerDelayMs: 10,
    });

    active = false;
    await vi.advanceTimersByTimeAsync(60);
    await promise;

    expect(speak).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("speaks live progress instead of a generic filler before the final reply", async () => {
    vi.useFakeTimers();
    const speak = vi.fn(async () => undefined);
    const promise = runVoiceTurnWithSpeech({
      runTurn: async (reportProgress) => {
        reportProgress("Thinking");
        await new Promise((resolve) => window.setTimeout(resolve, 50));
        reportProgress("Reading MAR.txt");
        return { speechText: "The file says testing." };
      },
      speechText: (result) => result.speechText,
      speak,
      fillerDelayMs: 10,
      selectFiller: () => "One moment.",
    });

    await vi.advanceTimersByTimeAsync(60);
    await promise;

    expect(speak).toHaveBeenCalledWith("Thinking", { bargeIn: false });
    expect(speak).toHaveBeenCalledWith("Reading MAR.txt", { bargeIn: false });
    expect(speak).not.toHaveBeenCalledWith("One moment.", { bargeIn: false });
    expect(speak).toHaveBeenLastCalledWith("The file says testing.", { bargeIn: true });
    vi.useRealTimers();
  });
});
