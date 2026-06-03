import { describe, expect, it } from "vitest";
import { outcomeFromTurnResult, outcomeFromError, speechTextFromTurnResult } from "./turnOutcome";

describe("outcomeFromError", () => {
  it("classifies a backend-unreachable error", () => {
    const o = outcomeFromError(new Error("request failed: connection refused"));
    expect(o.kind).toBe("backend_offline");
    expect(o.text.length).toBeGreaterThan(0);
  });
  it("classifies a generic error as error", () => {
    const o = outcomeFromError(new Error("invalid Core response: boom"));
    expect(o.kind).toBe("error");
  });
});

describe("outcomeFromTurnResult", () => {
  it("returns ok with the final text", () => {
    const o = outcomeFromTurnResult({ assistant_final_response: { text: "Hello there" } });
    expect(o.kind).toBe("ok");
    expect(o.text).toBe("Hello there");
  });
  it("maps a no-provider error", () => {
    const o = outcomeFromTurnResult({ error: { message: "no provider configured" } });
    expect(o.kind).toBe("no_provider");
  });
  it("maps a provider error", () => {
    const o = outcomeFromTurnResult({ error: { message: "provider upstream 500" } });
    expect(o.kind).toBe("provider_error");
  });
  it("maps an empty result distinctly", () => {
    const o = outcomeFromTurnResult({ assistant_final_response: { text: "" } });
    expect(o.kind).toBe("empty");
  });
});

describe("speechTextFromTurnResult", () => {
  it("returns final text only when the response is safe for speech", () => {
    expect(speechTextFromTurnResult({ assistant_final_response: { text: "Speak this", safe_for_speech: true } })).toBe("Speak this");
    expect(speechTextFromTurnResult({ assistant_final_response: { text: "Default safe" } })).toBe("Default safe");
  });

  it("blocks unsafe speech and error fallbacks from TTS", () => {
    expect(speechTextFromTurnResult({ assistant_final_response: { text: "Display only", safe_for_speech: false } })).toBe("");
    expect(speechTextFromTurnResult({ error: { message: "Provider failed with stack details" } })).toBe("");
  });

  it("removes markdown, citations, evidence labels, and links before TTS", () => {
    const text = [
      "**Answer:** see [docs](https://example.com/docs) [web.evidence.1]",
      "Raw source: https://example.com/source?q=1",
      "- `code` and _emphasis_ should not read symbols.",
    ].join("\n");
    expect(speechTextFromTurnResult({ assistant_final_response: { text } })).toBe(
      "Answer: see docs Raw source: code and emphasis should not read symbols.",
    );
  });
});
