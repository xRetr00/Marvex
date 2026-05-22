import { describe, expect, it } from "vitest";
import { finalTextFromTurnResult } from "./localTurn";

describe("local turn parsing", () => {
  it("extracts the assistant final text", () => {
    expect(finalTextFromTurnResult({ assistant_final_response: { text: "hello" } })).toBe("hello");
  });

  it("falls back to a safe error message", () => {
    expect(finalTextFromTurnResult({ error: { message: "failed safely" } })).toBe("failed safely");
  });
});
