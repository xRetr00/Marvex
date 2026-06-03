export type VoiceSpeak = (text: string, options?: { bargeIn?: boolean }) => Promise<unknown>;

export const VOICE_RESPONSE_FILLERS = ["One moment.", "Let me check.", "I'm checking."] as const;

export type VoiceTurnSpeechOptions<T> = {
  runTurn: () => Promise<T>;
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
  const scheduleFiller = typeof window !== "undefined" && fillerDelayMs >= 0;
  const timer = scheduleFiller
    ? window.setTimeout(() => {
        if (shouldSpeak?.() === false) return;
        const filler = selectFiller().trim();
        if (!filler) return;
        fillerState.promise = speak(filler, { bargeIn: false }).catch(() => undefined);
      }, fillerDelayMs)
    : undefined;

  let result: T;
  try {
    result = await runTurn();
  } finally {
    if (timer !== undefined) window.clearTimeout(timer);
  }

  if (fillerState.promise) await fillerState.promise.catch(() => undefined);
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
