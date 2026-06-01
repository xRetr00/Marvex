import { citationsFromTurnResult, stagesFromTurnResult, uiDirectivesFromTurnResult, type CitationRef, type TurnStage, type UiDirective } from "./localTurn";

export type TurnOutcomeKind =
  | "ok"
  | "empty"
  | "no_provider"
  | "provider_error"
  | "backend_offline"
  | "error";

export interface TurnOutcome {
  kind: TurnOutcomeKind;
  text: string;
  stages?: TurnStage[];
  directives?: UiDirective[];
  citations?: CitationRef[];
}

function lower(value: unknown): string {
  return typeof value === "string" ? value.toLowerCase() : "";
}

export function outcomeFromError(error: unknown): TurnOutcome {
  const message = error instanceof Error ? error.message : String(error);
  const m = message.toLowerCase();
  if (m.includes("chat turn cancelled") || m.includes("user_cancelled")) {
    return { kind: "empty", text: "" };
  }
  if (
    m.includes("connection refused") ||
    m.includes("connect") ||
    m.includes("request failed") ||
    m.includes("tauri bridge unavailable") ||
    m.includes("error sending request")
  ) {
    return { kind: "backend_offline", text: "Backend isn't running yet. Starting it — try again in a moment." };
  }
  return { kind: "error", text: message || "Request failed." };
}

export function outcomeFromTurnResult(payload: unknown): TurnOutcome {
  if (!payload || typeof payload !== "object") {
    return { kind: "error", text: "No response payload returned." };
  }
  const result = payload as {
    assistant_final_response?: { text?: unknown };
    error?: { message?: unknown };
  };
  const text = result.assistant_final_response?.text;
  if (typeof text === "string" && text.trim()) {
    return {
      kind: "ok",
      text,
      stages: stagesFromTurnResult(payload),
      directives: uiDirectivesFromTurnResult(payload),
      citations: citationsFromTurnResult(payload),
    };
  }
  const errMsg = result.error?.message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    const e = lower(errMsg);
    if (e.includes("no provider") || e.includes("not configured") || e.includes("no model")) {
      return { kind: "no_provider", text: "No model or provider is configured. Open Settings → Providers / Models to set one up." };
    }
    if (e.includes("provider") || e.includes("upstream") || e.includes("llm")) {
      return { kind: "provider_error", text: `Provider error: ${errMsg}` };
    }
    return { kind: "error", text: errMsg };
  }
  // Turn completed but produced no text.
  if (result.assistant_final_response && (text === "" || text === undefined)) {
    return { kind: "empty", text: "The assistant returned no response text." };
  }
  return { kind: "error", text: "No displayable response returned." };
}
