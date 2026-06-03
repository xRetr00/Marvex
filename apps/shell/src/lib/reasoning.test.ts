import { describe, expect, it } from "vitest";

import { splitReasoning, stripReasoning } from "./reasoning";

describe("splitReasoning", () => {
  it("returns the whole text as the answer when there is no think block", () => {
    expect(splitReasoning("Hello there")).toEqual({
      thinking: "",
      answer: "Hello there",
      thinkingStreaming: false,
    });
  });

  it("separates a closed think block from the answer", () => {
    const result = splitReasoning("<think>weigh options</think>The answer is 42.");
    expect(result.thinking).toBe("weigh options");
    expect(result.answer).toBe("The answer is 42.");
    expect(result.thinkingStreaming).toBe(false);
  });

  it("treats an unterminated think block as live streaming reasoning", () => {
    const result = splitReasoning("<think>still figuring this");
    expect(result.thinking).toBe("still figuring this");
    expect(result.answer).toBe("");
    expect(result.thinkingStreaming).toBe(true);
  });

  it("keeps prose that precedes the think block in the answer", () => {
    const result = splitReasoning("Sure.<think>reason</think> Done.");
    expect(result.thinking).toBe("reason");
    expect(result.answer).toBe("Sure. Done.");
  });

  it("collects multiple think blocks (multi-tool turns) and keeps the answer", () => {
    const result = splitReasoning("<think>step one</think>Doing X.<think>step two</think>Final answer.");
    expect(result.thinking).toBe("step one\nstep two");
    expect(result.answer).toBe("Doing X.Final answer.");
    expect(result.thinkingStreaming).toBe(false);
  });

  it("stripReasoning removes the think block for speech/copy", () => {
    expect(stripReasoning("<think>secret</think>Spoken answer.")).toBe("Spoken answer.");
    expect(stripReasoning("No tags here")).toBe("No tags here");
  });
});
