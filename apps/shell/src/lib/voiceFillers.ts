// Voice-only "thinking" fillers.
//
// In voice mode the assistant speaks live progress (see ChatApp `onProgress`).
// The first progress event is usually a generic status label such as "Thinking"
// or "Working" (from activityLabels.ts). Spoken verbatim that sounds robotic —
// and because the model-commentary gate then suppresses later labels, the user
// heard a flat "Thinking" followed by silence until the final answer.
//
// Instead we speak ONE playful, natural filler for those content-free status
// labels and stay quiet for the rest, while the on-screen activity chips keep
// their precise labels untouched. Meaningful labels ("Searching the web",
// "Reading config.ts") still pass through as spoken narration.

export const VOICE_THINKING_FILLERS = [
  "Let me put my thinking cap on…",
  "Cracking my knuckles — give me a sec…",
  "Brain cells, assemble…",
  "On it — let me work a little magic…",
  "Hmm, let me noodle on this…",
  "Spinning up the gears…",
  "Alright, let me dig into that…",
  "let's see what we got here…",
  "Putting the pieces together…",
  "Let me chew on that for a moment…",
] as const;

// Generic, information-free status labels emitted by activityLabels.ts. These
// are the ones worth swapping for a friendly filler when spoken. Labels that
// carry real signal ("Searching the web", "Waiting for approval", any tool
// label with a target) are intentionally left to speak as-is.
export const GENERIC_THINKING_LABELS: ReadonlySet<string> = new Set([
  "Thinking",
  "Working",
  "Using tools",
  "Connecting to MCP",
  "Loading skills",
]);

// Short acknowledgements spoken the moment Marvex starts listening for a voice
// command (the "I heard you, go ahead" cue). Kept brief and natural — like the
// fillers, but snappier since the user is about to speak.
export const LISTENING_CUES = [
  "Yeah?",
  "I'm here.",
  "Go ahead.",
  "Mm-hm?",
  "Listening.",
  "What's up?",
  "Yes?",
  "All ears.",
  "Hit me.",
  "Ready.",
] as const;

/** Pick a playful filler, avoiding an immediate repeat of `previous`. */
export function pickVoiceFiller(previous?: string): string {
  return pickRandom(VOICE_THINKING_FILLERS, previous);
}

/** Pick a short listening cue, avoiding an immediate repeat of `previous`. */
export function pickListeningCue(previous?: string): string {
  return pickRandom(LISTENING_CUES, previous);
}

function pickRandom(pool: readonly string[], previous?: string): string {
  const choices = pool.filter((item) => item !== previous);
  const source = choices.length > 0 ? choices : pool;
  return source[Math.floor(Math.random() * source.length)];
}

export interface VoiceProgressContext {
  /** Whether a thinking filler has already been spoken this turn. */
  fillerSpoken: boolean;
  /** The last filler spoken this turn, to avoid back-to-back repeats. */
  previousFiller: string;
}

export interface VoiceProgressSpeech {
  /** The text to speak (empty when skipped). */
  text: string;
  /** True when `text` is a generic-thinking filler we substituted in. */
  isFiller: boolean;
  /** True when nothing should be spoken for this progress event. */
  skip: boolean;
}

/**
 * Decide what (if anything) to speak for a progress label in voice mode.
 *
 * - A generic status label becomes a single playful filler the first time, then
 *   is silently dropped so we don't chatter through "Thinking → Working → …".
 * - Anything else (tool narration, model commentary) is spoken unchanged.
 */
export function voiceProgressSpeech(label: string, context: VoiceProgressContext): VoiceProgressSpeech {
  const trimmed = label.trim();
  if (GENERIC_THINKING_LABELS.has(trimmed)) {
    if (context.fillerSpoken) return { text: "", isFiller: true, skip: true };
    return { text: pickVoiceFiller(context.previousFiller), isFiller: true, skip: false };
  }
  return { text: label, isFiller: false, skip: false };
}
