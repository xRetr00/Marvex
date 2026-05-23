export function finalTextFromTurnResult(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "No response payload returned.";
  const result = payload as { assistant_final_response?: { text?: unknown }; error?: { message?: unknown } };
  const text = result.assistant_final_response?.text;
  if (typeof text === "string" && text.trim()) return text;
  const error = result.error?.message;
  if (typeof error === "string" && error.trim()) return error;
  return "No displayable response returned.";
}

export interface TurnStage {
  stage_name: string;
  status: string;
}

/** Extract the per-stage reasoning trace from a turn result (drives chain-of-thought). */
export function stagesFromTurnResult(payload: unknown): TurnStage[] {
  if (!payload || typeof payload !== "object") return [];
  const summaries = (payload as { stage_summaries?: unknown }).stage_summaries;
  if (!Array.isArray(summaries)) return [];
  return summaries
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null;
      const stage = entry as { stage_name?: unknown; status?: unknown };
      if (typeof stage.stage_name !== "string") return null;
      return { stage_name: stage.stage_name, status: typeof stage.status === "string" ? stage.status : "completed" };
    })
    .filter((s): s is TurnStage => s !== null);
}
