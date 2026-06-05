export type ProviderUsage = {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cachedInputTokens: number;
  reasoningTokens: number;
};

export const emptyProviderUsage: ProviderUsage = {
  inputTokens: 0,
  outputTokens: 0,
  totalTokens: 0,
  cachedInputTokens: 0,
  reasoningTokens: 0,
};

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : 0;
}

export function providerUsageFromTurnResult(payload: unknown): ProviderUsage {
  if (!payload || typeof payload !== "object") {
    return { ...emptyProviderUsage };
  }
  const metadata = (payload as { metadata?: unknown }).metadata;
  const usage = metadata && typeof metadata === "object"
    ? (metadata as { provider_usage?: unknown }).provider_usage
    : undefined;
  const row = usage && typeof usage === "object" ? usage as Record<string, unknown> : {};
  const inputDetails = row.input_tokens_details && typeof row.input_tokens_details === "object"
    ? row.input_tokens_details as Record<string, unknown>
    : {};
  const outputDetails = row.output_tokens_details && typeof row.output_tokens_details === "object"
    ? row.output_tokens_details as Record<string, unknown>
    : {};
  return {
    inputTokens: numberValue(row.input_tokens ?? row.prompt_tokens),
    outputTokens: numberValue(row.output_tokens ?? row.completion_tokens),
    totalTokens: numberValue(row.total_tokens),
    cachedInputTokens: numberValue(inputDetails.cached_tokens ?? row.cache_read_input_tokens),
    reasoningTokens: numberValue(outputDetails.reasoning_tokens),
  };
}

export function addProviderUsage(current: ProviderUsage, next: ProviderUsage): ProviderUsage {
  return {
    inputTokens: current.inputTokens + next.inputTokens,
    outputTokens: current.outputTokens + next.outputTokens,
    totalTokens: current.totalTokens + next.totalTokens,
    cachedInputTokens: current.cachedInputTokens + next.cachedInputTokens,
    reasoningTokens: current.reasoningTokens + next.reasoningTokens,
  };
}

export function formatTokenCount(value: number): string {
  if (value < 1000) return String(Math.round(value));
  if (value < 1_000_000) return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0).replace(/\.0$/, "")}K`;
  return `${(value / 1_000_000).toFixed(value < 10_000_000 ? 1 : 0).replace(/\.0$/, "")}M`;
}
