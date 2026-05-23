import { describe, expect, it } from "vitest";
import { outcomeFromTurnResult, outcomeFromError } from "./turnOutcome";

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
