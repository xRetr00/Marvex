export function finalTextFromTurnResult(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "No response payload returned.";
  const result = payload as { assistant_final_response?: { text?: unknown }; error?: { message?: unknown } };
  const text = result.assistant_final_response?.text;
  if (typeof text === "string" && text.trim()) return text;
  const error = result.error?.message;
  if (typeof error === "string" && error.trim()) return error;
  return "No displayable response returned.";
}
