import { describe, expect, it } from "vitest";
import { providerResponseIdFromTurnResult } from "./turnResultHelpers";

describe("providerResponseIdFromTurnResult", () => {
  it("returns the first non-empty ref_id from provider_turn_refs", () => {
    const result = {
      provider_turn_refs: [
        { ref_id: "  resp-001  " },
        { ref_id: "resp-002" },
      ],
    };
    expect(providerResponseIdFromTurnResult(result)).toBe("resp-001");
  });

  it("skips the synthetic ':provider-turn' fallback id", () => {
    const result = {
      provider_turn_refs: [
        { ref_id: "turn-shell-chat-123:provider-turn" },
        { ref_id: "chatcmpl-abc" },
      ],
    };
    expect(providerResponseIdFromTurnResult(result)).toBe("chatcmpl-abc");
  });

  it("returns undefined when the only ref is the synthetic fallback", () => {
    const result = {
      provider_turn_refs: [{ ref_id: "turn-x:provider-turn" }],
    };
    expect(providerResponseIdFromTurnResult(result)).toBeUndefined();
  });

  it("returns undefined when the turn carries an error envelope", () => {
    const result = {
      error: { code: "PROVIDER_ERROR", message: "boom" },
      provider_turn_refs: [{ ref_id: "chatcmpl-zzz" }],
    };
    expect(providerResponseIdFromTurnResult(result)).toBeUndefined();
  });

  it("returns undefined for non-object results", () => {
    expect(providerResponseIdFromTurnResult(null)).toBeUndefined();
    expect(providerResponseIdFromTurnResult(undefined)).toBeUndefined();
    expect(providerResponseIdFromTurnResult("nope")).toBeUndefined();
    expect(providerResponseIdFromTurnResult(123)).toBeUndefined();
  });

  it("returns undefined when provider_turn_refs is missing", () => {
    expect(providerResponseIdFromTurnResult({})).toBeUndefined();
  });

  it("ignores refs with empty or whitespace-only ids", () => {
    const result = {
      provider_turn_refs: [
        { ref_id: "" },
        { ref_id: "   " },
        { ref_id: "real-id" },
      ],
    };
    expect(providerResponseIdFromTurnResult(result)).toBe("real-id");
  });
});
