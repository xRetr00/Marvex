import { describe, expect, it } from "vitest";
import { formatTokenCount, providerUsageFromTurnResult } from "./providerUsage";

describe("provider usage", () => {
  it("reads Responses API usage from turn metadata", () => {
    expect(providerUsageFromTurnResult({
      metadata: {
        provider_usage: {
          input_tokens: 1200,
          output_tokens: 80,
          total_tokens: 1280,
          input_tokens_details: { cached_tokens: 240 },
          output_tokens_details: { reasoning_tokens: 32 },
        },
      },
    })).toEqual({
      inputTokens: 1200,
      outputTokens: 80,
      totalTokens: 1280,
      cachedInputTokens: 240,
      reasoningTokens: 32,
    });
  });

  it("formats compact context counts", () => {
    expect(formatTokenCount(1240)).toBe("1.2K");
    expect(formatTokenCount(128000)).toBe("128K");
  });
});
