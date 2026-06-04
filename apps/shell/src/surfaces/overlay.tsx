import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { listen } from "../lib/tauriBridge";
import { useBackendStatus, type WakewordState } from "../lib/backendStatus";
import {
  displayDetail,
  idleAssistantState,
  normalizeAssistantState,
  shouldShowOverlay,
  statusLabel,
  waveformLevel,
  type AssistantStateEvent,
} from "../lib/assistantState";
import { createChatSession, listChatSessions, setOverlaySize, showChat, submitChatTurnStream, type OverlayWindowSize } from "../lib/shellCommands";
import { persistMode } from "../lib/modeStore";
import { createIslandQueue, type IslandCard, type IslandQueueSnapshot } from "../lib/islandQueue";
import { fetchPendingApprovals, type ApprovalSummary } from "../lib/controlPlaneClient";
import { speechTextFromTurnResult } from "../lib/turnOutcome";
import { providerResponseIdFromTurnResult } from "../lib/turnResultHelpers";
import { fetchVoiceWorkerStatus, speakVoiceWorker, transcriptFromStatus } from "../lib/voiceControlClient";
import { runVoiceTurnWithSpeech } from "../lib/voiceTurnSpeech";
import { activityLabel } from "../lib/activityLabels";
import DynamicIsland from "@/components/dynamic-island/DynamicIsland";
import { IslandWaveform } from "@/components/dynamic-island/IslandWaveform";
import { ApprovalCard } from "@/components/dynamic-island/cards/ApprovalCard";
import { InfoCard } from "@/components/dynamic-island/cards/InfoCard";
import { ISLAND_GEOMETRY } from "@/components/dynamic-island/geometry.generated";
import "./overlay.css";

// Warm cream shimmer for the status label. Injected once.
if (typeof document !== "undefined" && !document.getElementById("marvex-shimmer-style")) {
  const style = document.createElement("style");
  style.id = "marvex-shimmer-style";
  style.textContent = `@keyframes marvex-shimmer{0%{background-position:0% center}100%{background-position:200% center}}`;
  document.head.appendChild(style);
}

const SHIMMER_STYLE: React.CSSProperties = {
  background: "linear-gradient(90deg, #ffe0c2 0%, #fff7ee 45%, #ffe0c2 85%)",
  backgroundSize: "200% auto",
  WebkitBackgroundClip: "text",
  WebkitTextFillColor: "transparent",
  backgroundClip: "text",
  animation: "marvex-shimmer 2.4s linear infinite",
  fontSize: "0.72rem",
  fontWeight: 600,
  letterSpacing: "0.02em",
  whiteSpace: "nowrap",
};

const OVERLAY_SHADOW_PADDING = ISLAND_GEOMETRY.shadowPadding;

type OverlayBounds = { width: number; height: number };

export function toOverlayWindowSize(bounds: OverlayBounds, padding = OVERLAY_SHADOW_PADDING): OverlayWindowSize {
  return {
    width: Math.max(1, Math.round(bounds.width) + padding * 2),
    height: Math.max(1, Math.round(bounds.height) + padding * 2),
  };
}

function sizesClose(a: OverlayWindowSize | null, b: OverlayWindowSize) {
  return Boolean(a && Math.abs(a.width - b.width) <= 1 && Math.abs(a.height - b.height) <= 1);
}

function TextShimmer({ text }: { text: string }) {
  return (
    <motion.span key={text} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }} style={SHIMMER_STYLE}>
      {text}
    </motion.span>
  );
}

function wakewordStatusText(status: WakewordState | undefined): string {
  if (status === "running" || status === "enabled") return "Hey Marvex on";
  if (status === "not_ready") return "Wake setup";
  if (status === "disabled") return "Wake off";
  return "Wake checking";
}

function approvalCard(approval: ApprovalSummary): IslandCard {
  return {
    id: `approval-${approval.approval_request_id}`,
    kind: "approval",
    title: "Approval Required",
    body: approval.user_visible_summary,
    autoDismiss: false,
    payload: approval,
  };
}

export function OverlaySurface() {
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const backend = useBackendStatus();
  const [cardState, setCardState] = useState<IslandQueueSnapshot>({ active: null, queued: [] });
  const [manualExpand, setManualExpand] = useState(false);
  const phaseRef = useRef(0);
  const [phase, setPhase] = useState(0);
  const islandRef = useRef<HTMLDivElement | null>(null);
  const lastOverlaySizeRef = useRef<OverlayWindowSize | null>(null);
  const prevStatusRef = useRef<string>("idle");
  const overlaySessionIdRef = useRef<string | null>(null);
  const previousResponseIdsRef = useRef<Record<string, string>>({});
  const lastVoiceEventRef = useRef("");

  const queueRef = useRef<ReturnType<typeof createIslandQueue> | null>(null);
  if (!queueRef.current) {
    queueRef.current = createIslandQueue({ maxQueue: 4, onChange: setCardState });
  }
  const queue = queueRef.current;

  // Drive the phase counter so pulse/animated statuses keep moving.
  useEffect(() => {
    let rafId: number;
    const tick = () => {
      phaseRef.current += 0.05;
      setPhase(phaseRef.current);
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, []);

  // Welcome card collapses back into the idle pill after its lifecycle.
  useEffect(() => {
    const t = setTimeout(() => {
      queue.show({ id: "welcome", kind: "info", title: "Marvex is ready", body: "Say \"Hey Marvex\" or click the island to chat.", duration: 5000 });
    }, 1200);
    return () => clearTimeout(t);
  }, [queue]);

  // Assistant-state stream → state + approval cards. (No click-through, no
  // voice-decision listener: voice is visualized, the worker owns the mic.)
  useEffect(() => {
    let cleanup: VoidFunction | undefined;
    void listen("assistant-state", (event) => {
      let next: AssistantStateEvent;
      try {
        next = normalizeAssistantState(event.payload);
      } catch {
        next = idleAssistantState;
      }
      setState(next);
      if (next.status === "needs_approval" && prevStatusRef.current !== "needs_approval") {
        void fetchPendingApprovals()
          .then((approvals) => {
            if (approvals[0]) queue.show(approvalCard(approvals[0]), { force: true });
          })
          .catch(() => undefined);
      }
      prevStatusRef.current = next.status;
    }).then((unlisten) => {
      cleanup = unlisten;
    });
    return () => cleanup?.();
  }, [queue]);

  const ensureOverlaySession = async (): Promise<string> => {
    if (overlaySessionIdRef.current) return overlaySessionIdRef.current;
    const existing = await listChatSessions().catch(() => ({ sessions: [] }));
    const session = existing.sessions[0] ?? (await createChatSession("Overlay voice")).session;
    const sessionId = session.session_ref.ref_id;
    overlaySessionIdRef.current = sessionId;
    return sessionId;
  };

  const runOverlayVoiceTurn = async (text: string) => {
    await runVoiceTurnWithSpeech({
      runTurn: async (reportProgress) => {
        const sessionId = await ensureOverlaySession();
        const result = await submitChatTurnStream(
          text,
          { session_id: sessionId },
          previousResponseIdsRef.current[sessionId],
          {
            onDelta: () => undefined,
            onTool: (event) => {
              if (event.phase === "end") return;
              reportProgress(activityLabel({
                id: event.id || event.name || "tool",
                name: event.name ?? "",
                arguments: event.arguments,
                active: true,
              }));
            },
            onStatus: (event) => {
              const status = String(event.status ?? "").trim();
              if (!["thinking", "working", "using_tools", "mcp", "skills", "searching_web"].includes(status)) return;
              reportProgress(activityLabel({ id: `status.${status}`, name: `status.${status}`, active: true }));
            },
          },
        );
        const nextProviderResponseId = providerResponseIdFromTurnResult(result);
        if (nextProviderResponseId) previousResponseIdsRef.current[sessionId] = nextProviderResponseId;
        return result;
      },
      speechText: speechTextFromTurnResult,
      speak: speakVoiceWorker,
    });
  };

  const wakewordActive = backend?.wakeword === "enabled" || backend?.wakeword === "running";
  useEffect(() => {
    if (!wakewordActive) return;
    let cancelled = false;
    let busy = false;
    const timer = window.setInterval(() => {
      if (busy) return;
      busy = true;
      void Promise.resolve(fetchVoiceWorkerStatus())
        .then(async (status) => {
          if (cancelled) return;
          const transcript = transcriptFromStatus(status);
          if (!transcript || transcript.eventId === lastVoiceEventRef.current) return;
          lastVoiceEventRef.current = transcript.eventId;
          await runOverlayVoiceTurn(transcript.text);
        })
        .catch(() => undefined)
        .finally(() => {
          busy = false;
        });
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [wakewordActive]);

  const audioLevel = waveformLevel(state, phase);
  const isActive = shouldShowOverlay(state);
  const statusText = displayDetail(state);
  const wakeText = wakewordStatusText(backend?.wakeword);
  const activeCard = cardState.active;
  const expanded = Boolean(activeCard) || isActive || manualExpand;
  const view = expanded ? "expanded" : "idle";

  // Keep the native window sized to the pill (+ shadow padding) as it morphs.
  useLayoutEffect(() => {
    const island = islandRef.current;
    if (!island) return;
    let frame = 0;
    const updateSize = () => {
      frame = 0;
      const rect = island.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const next = toOverlayWindowSize(rect);
      if (sizesClose(lastOverlaySizeRef.current, next)) return;
      lastOverlaySizeRef.current = next;
      // Match the native window's rounded-region radius to the pill's visual
      // radius so the clip hugs the pill exactly (no white corner slivers).
      const radius = expanded ? ISLAND_GEOMETRY.expanded.radius : ISLAND_GEOMETRY.idle.radius;
      void setOverlaySize(next, radius).catch(() => undefined);
    };
    const scheduleUpdate = () => {
      if (frame) return;
      frame = requestAnimationFrame(updateSize);
    };
    scheduleUpdate();
    const resizeObserver = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(scheduleUpdate);
    resizeObserver?.observe(island);
    window.addEventListener("resize", scheduleUpdate);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      resizeObserver?.disconnect();
      window.removeEventListener("resize", scheduleUpdate);
    };
  }, [activeCard?.id, expanded, isActive, state.status, statusText]);

  const openChat = () => {
    persistMode("chat");
    void showChat().catch(() => undefined);
  };

  return (
    <div className="overlay-shell">
      <div
        ref={islandRef}
        className="marvex-island"
        style={{ width: "fit-content", cursor: "pointer" }}
        onClick={() => setManualExpand((v) => !v)}
        title="Marvex"
      >
        <DynamicIsland
          view={view}
          idleContent={
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, width: "100%", justifyContent: "center" }}>
              <motion.span
                animate={{ opacity: [0.45, 0.9, 0.45] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
                style={{ width: 7, height: 7, borderRadius: "50%", background: "#ffe0c2", display: "block", flex: "0 0 auto" }}
              />
              <span style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
                <span style={idleLabelStyle}>{statusLabel(state.status)}</span>
                <span style={wakeLabelStyle}>{wakeText}</span>
              </span>
              <IslandWaveform variant="compact" audioLevel={audioLevel} active={isActive} />
            </div>
          }
          expandedContent={
            activeCard ? (
              <IslandCardView card={activeCard} onDismiss={() => queue.dismiss(activeCard.id)} />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "stretch", gap: 8, width: "100%" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                  <AnimatePresence mode="wait">
                    <TextShimmer text={statusText} key={statusText} />
                  </AnimatePresence>
                  <button
                    type="button"
                    aria-label="Open Marvex chat"
                    onClick={(e) => { e.stopPropagation(); openChat(); }}
                    style={chevronStyle}
                  >
                    ⌃
                  </button>
                </div>
                <IslandWaveform variant="expanded" audioLevel={audioLevel} active={isActive || manualExpand} />
                <div style={wakeRowStyle}>{wakeText}</div>
              </div>
            )
          }
        />
      </div>
    </div>
  );
}

function IslandCardView({ card, onDismiss }: { card: IslandCard; onDismiss: () => void }) {
  if (card.kind === "approval" && card.payload) {
    return <ApprovalCard approval={card.payload as ApprovalSummary} onDone={onDismiss} />;
  }
  return <InfoCard title={card.title ?? "Marvex"} body={card.body} onDismiss={onDismiss} />;
}

const idleLabelStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.01em",
  color: "rgba(255,224,194,0.9)",
  whiteSpace: "nowrap",
};

const wakeLabelStyle: React.CSSProperties = {
  fontSize: 9,
  fontWeight: 600,
  letterSpacing: "0.01em",
  color: "rgba(255,224,194,0.58)",
  whiteSpace: "nowrap",
};

const wakeRowStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  color: "rgba(255,224,194,0.62)",
  whiteSpace: "nowrap",
};

const chevronStyle: React.CSSProperties = {
  border: 0,
  borderRadius: 999,
  width: 22,
  height: 22,
  flexShrink: 0,
  display: "grid",
  placeItems: "center",
  background: "rgba(255,255,255,0.09)",
  boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.10)",
  color: "#ffe0c2",
  fontSize: 13,
  cursor: "pointer",
  lineHeight: 1,
};
