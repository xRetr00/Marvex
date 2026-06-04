export type VoiceSpeak = (text: string, options?: { bargeIn?: boolean }) => Promise<unknown>;

export const VOICE_RESPONSE_FILLERS = ["One moment.", "Let me check.", "I'm checking."] as const;

export type VoiceTurnSpeechOptions<T> = {
  runTurn: (reportProgress: (text: string) => void) => Promise<T>;
  speechText: (result: T) => string;
  speak: VoiceSpeak;
  shouldSpeak?: () => boolean;
  fillerDelayMs?: number;
  selectFiller?: () => string;
};

export async function runVoiceTurnWithSpeech<T>({
  runTurn,
  speechText,
  speak,
  shouldSpeak,
  fillerDelayMs = 700,
  selectFiller = randomVoiceResponseFiller,
}: VoiceTurnSpeechOptions<T>): Promise<T> {
  const fillerState: { promise?: Promise<unknown> } = {};
  const progressState: { promise?: Promise<unknown>; spoken: Set<string> } = { spoken: new Set() };
  const scheduleFiller = typeof window !== "undefined" && fillerDelayMs >= 0;
  let timer: number | undefined;
  const reportProgress = (text: string) => {
    if (shouldSpeak?.() === false) return;
    const progress = text.replace(/\s+/g, " ").trim();
    const key = progress.toLowerCase();
    if (!progress || progressState.spoken.has(key)) return;
    progressState.spoken.add(key);
    if (timer !== undefined) window.clearTimeout(timer);
    const previous = progressState.promise ?? Promise.resolve();
    progressState.promise = previous
      .then(() => speak(progress, { bargeIn: false }))
      .catch(() => undefined);
  };
  timer = scheduleFiller
    ? window.setTimeout(() => {
        if (shouldSpeak?.() === false) return;
        if (progressState.spoken.size > 0) return;
        const filler = selectFiller().trim();
        if (!filler) return;
        fillerState.promise = speak(filler, { bargeIn: false }).catch(() => undefined);
      }, fillerDelayMs)
    : undefined;

  let result: T;
  try {
    result = await runTurn(reportProgress);
  } finally {
    if (timer !== undefined) window.clearTimeout(timer);
  }

  if (fillerState.promise) await fillerState.promise.catch(() => undefined);
  if (progressState.promise) await progressState.promise.catch(() => undefined);
  if (shouldSpeak?.() === false) return result;

  const reply = speechText(result).trim();
  if (reply) {
    await speak(reply, { bargeIn: true }).catch(() => undefined);
  }
  return result;
}

function randomVoiceResponseFiller(): string {
  return VOICE_RESPONSE_FILLERS[Math.floor(Math.random() * VOICE_RESPONSE_FILLERS.length)];
}
