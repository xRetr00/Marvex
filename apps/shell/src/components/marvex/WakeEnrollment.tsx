import { useCallback, useEffect, useState } from "react";
import { Mic, Check, Loader2, Trash2 } from "lucide-react";
import { recordWakeReference, fetchVoiceWorkerStatus, type VoiceWorkerStatus } from "@/lib/voiceControlClient";

const TARGET_SAMPLES = 6;
const PHRASE = "Hey Marvex";

/** Pull the running reference count out of the worker's latest record event. */
function referenceCountFromStatus(status: VoiceWorkerStatus | null): number | null {
  const events = status?.recent_events;
  if (!Array.isArray(events)) return null;
  for (let i = events.length - 1; i >= 0; i--) {
    const summary = (events[i] as { summary?: Record<string, unknown> })?.summary;
    if (summary && summary.record_wake_reference === true && typeof summary.reference_count === "number") {
      return summary.reference_count as number;
    }
  }
  return null;
}

function lastRecordReason(status: VoiceWorkerStatus | null): string | null {
  const events = status?.recent_events;
  if (!Array.isArray(events)) return null;
  for (let i = events.length - 1; i >= 0; i--) {
    const summary = (events[i] as { summary?: Record<string, unknown> })?.summary;
    if (summary && summary.record_wake_reference === true) {
      return (summary.reason_code as string) ?? null;
    }
  }
  return null;
}

/**
 * In-app "Hey Marvex" enrollment for the local-wake backend. Records a few
 * reference samples (the worker VAD-endpoints each utterance and saves a WAV);
 * local-wake matches live audio against them via embedding + DTW. No training.
 */
export function WakeEnrollment() {
  const [count, setCount] = useState<number>(0);
  const [recording, setRecording] = useState(false);
  const [message, setMessage] = useState<string>("");

  const refresh = useCallback(async () => {
    try {
      const status = await fetchVoiceWorkerStatus();
      const c = referenceCountFromStatus(status);
      if (c !== null) setCount(c);
    } catch {
      /* worker not up yet */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const record = useCallback(async () => {
    if (recording) return;
    setRecording(true);
    setMessage("Listening — say “Hey Marvex” now…");
    try {
      const status = await recordWakeReference(PHRASE);
      const reason = lastRecordReason(status);
      const c = referenceCountFromStatus(status);
      if (reason === "no_speech") {
        setMessage("Didn't catch that — speak right after pressing Record.");
      } else if (reason === "continuous_capture_active") {
        setMessage("Turn off the mic/wake listener first, then record.");
      } else {
        if (c !== null) setCount(c);
        setMessage("Saved ✓");
      }
    } catch (error) {
      setMessage(`Recording failed: ${String(error)}`);
    } finally {
      setRecording(false);
    }
  }, [recording]);

  const done = count >= TARGET_SAMPLES;

  return (
    <div style={{ maxWidth: 560, margin: "0 auto", display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--foreground)" }}>Wake word: "Hey Marvex"</h2>
        <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--muted-foreground)", lineHeight: 1.5 }}>
          Record {TARGET_SAMPLES} short samples of "Hey Marvex" so Marvex learns your voice. Press Record, then say it once,
          normally. Vary it a little (a bit faster/slower, from your normal seat). No training, all local.
        </p>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {Array.from({ length: TARGET_SAMPLES }).map((_, i) => (
          <div key={i} title={`Sample ${i + 1}`} style={{
            flex: 1, height: 8, borderRadius: 999,
            background: i < count ? "#34d399" : "color-mix(in srgb, var(--foreground) 14%, transparent)",
            transition: "background 0.2s",
          }} />
        ))}
      </div>
      <div style={{ fontSize: 12, color: "var(--muted-foreground)" }}>{count} / {TARGET_SAMPLES} samples recorded</div>

      <button
        onClick={() => void record()}
        disabled={recording}
        style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          height: 44, borderRadius: 12, border: "1px solid var(--border)", cursor: recording ? "default" : "pointer",
          background: done ? "color-mix(in srgb, #34d399 18%, var(--card))" : "var(--card)",
          color: "var(--foreground)", fontSize: 13, fontWeight: 650, opacity: recording ? 0.75 : 1,
        }}
      >
        {recording ? <Loader2 size={16} className="animate-spin" /> : done ? <Check size={16} /> : <Mic size={16} />}
        {recording ? "Listening…" : done ? "Record another (optional)" : "Record sample"}
      </button>

      {message && (
        <div style={{ fontSize: 12, color: "var(--muted-foreground)", minHeight: 16 }}>{message}</div>
      )}

      {done && (
        <div style={{ fontSize: 12, color: "#34d399", display: "flex", alignItems: "center", gap: 6 }}>
          <Check size={14} /> Enrollment complete. Turn on the mic and try saying "Hey Marvex".
        </div>
      )}

      <p style={{ margin: "4px 0 0", fontSize: 11, color: "var(--muted-foreground)", display: "flex", alignItems: "center", gap: 6 }}>
        <Trash2 size={12} /> To re-enroll, delete the files in the wake-references folder and record again.
      </p>
    </div>
  );
}
