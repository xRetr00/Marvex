import { z } from "zod";

export const assistantStatusKinds = [
  "idle",
  "listening",
  "thinking",
  "working",
  "using_tools",
  "mcp",
  "skills",
  "searching_web",
  "talking",
  "asking",
  "needs_approval"
] as const;

export const assistantStatusKindSchema = z.enum(assistantStatusKinds);

export const assistantStateEventSchema = z.object({
  schema_version: z.union([z.string(), z.number()]).transform(String),
  ts: z.string(),
  status: assistantStatusKindSchema,
  detail: z.string().nullable().optional(),
  audio_level: z.number().min(0).max(1).default(0),
  session_ref: z.string().nullable().optional(),
  trace_id: z.string().nullable().optional(),
  raw_audio_persisted: z.literal(false).default(false)
});

export type AssistantStatusKind = (typeof assistantStatusKinds)[number];
export type AssistantStateEvent = z.infer<typeof assistantStateEventSchema>;

export const idleAssistantState: AssistantStateEvent = {
  schema_version: "1",
  ts: new Date(0).toISOString(),
  status: "idle",
  detail: null,
  audio_level: 0,
  session_ref: null,
  trace_id: null,
  raw_audio_persisted: false
};

const labels: Record<AssistantStatusKind, string> = {
  idle: "Idle",
  listening: "Listening",
  thinking: "Thinking",
  working: "Working",
  using_tools: "Using Tools",
  mcp: "MCP",
  skills: "Skills",
  searching_web: "Searching Web",
  talking: "Talking",
  asking: "Asking",
  needs_approval: "Needs Approval"
};

export function statusLabel(status: AssistantStatusKind): string {
  return labels[status];
}

export function normalizeAssistantState(value: unknown): AssistantStateEvent {
  return assistantStateEventSchema.parse(value);
}

export function shouldShowOverlay(state: AssistantStateEvent): boolean {
  return state.status !== "idle";
}

export function displayDetail(state: AssistantStateEvent): string {
  const detail = state.detail?.trim();
  return detail ? prettyStatusDetail(detail) : statusLabel(state.status);
}

function prettyStatusDetail(detail: string): string {
  return detail.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function waveformLevel(state: AssistantStateEvent, phase = 0): number {
  switch (state.status) {
    case "idle":
      return 0;
    case "listening":
    case "talking":
      // Real microphone / TTS amplitude drives the bands directly.
      return clamp(state.audio_level);
    case "needs_approval":
    case "asking":
      // Gentle attention pulse while waiting on the user.
      return clamp(0.16 + Math.sin(phase) * 0.05);
    default:
      // thinking, working, using_tools, mcp, skills, searching_web:
      // a lively animated baseline so the waveform stays alive during work.
      return clamp(0.22 + Math.sin(phase) * 0.07);
  }
}

function clamp(value: number): number {
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}
