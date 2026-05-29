import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { listen } from "../lib/tauriBridge";
import {
  displayDetail,
  idleAssistantState,
  normalizeAssistantState,
  shouldShowOverlay,
  type AssistantStateEvent,
  waveformLevel,
} from "../lib/assistantState";
import { resumeApprovalTurn, setOverlayClickThrough, setOverlaySize, showChat, type OverlayWindowSize } from "../lib/shellCommands";
import { persistMode } from "../lib/modeStore";
import { makeHoverEdgeTrigger } from "../lib/overlayHover";
import { createIslandQueue, type IslandCard, type IslandQueueSnapshot } from "../lib/islandQueue";
import { decideApproval, fetchPendingApprovals, type ApprovalSummary } from "../lib/controlPlaneClient";
import DynamicIsland from "@/components/dynamic-island";
import { MarvexWaveform } from "@/components/waveform-shader/MarvexWaveform";
import { AnimatePresence, motion } from "framer-motion";
import "./overlay.css";

// Warm shimmer (Marvex cream gradient) for the status text. Injected once.
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

const OVERLAY_SHADOW_PADDING = 8;

type OverlayBounds = {
  width: number;
  height: number;
};

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
    <motion.span
      key={text}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      style={SHIMMER_STYLE}
    >
      {text}
    </motion.span>
  );
}

// Edge-triggered hover updater: prevents redundant IPC calls when the browser
// fires repeated mouseenter/mouseleave events on the same state.
const hoverEdgeTrigger = makeHoverEdgeTrigger((over: boolean) => {
  void setOverlayClickThrough(!over).catch(() => undefined);
});

export function OverlaySurface() {
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const [hovered, setHovered] = useState(false);
  const [cardState, setCardState] = useState<IslandQueueSnapshot>({ active: null, queued: [] });
  // Animated phase counter for statuses that use Math.sin(phase) in waveformLevel.
  const phaseRef = useRef<number>(0);
  const [phase, setPhase] = useState(0);
  const islandRef = useRef<HTMLDivElement | null>(null);
  const queueRef = useRef<ReturnType<typeof createIslandQueue> | null>(null);
  if (!queueRef.current) {
    queueRef.current = createIslandQueue({ maxQueue: 4, onChange: setCardState });
  }
  const queue = queueRef.current;
  const lastOverlaySizeRef = useRef<OverlayWindowSize | null>(null);

  // Drive the phase counter for pulse-animated statuses (needs_approval, asking,
  // thinking, working, etc.) so waveformLevel(state, phase) produces a live
  // animated value instead of a frozen Math.sin(0) result.
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

  // OverlayDocumentScope in App.tsx already adds these classes before
  // OverlaySurface mounts. This effect is intentionally omitted to avoid
  // duplicate class management and premature removal on teardown.

  // Welcome card: lives inside the island overlay and collapses back into the
  // idle pill after its own lifecycle.
  useEffect(() => {
    const t = setTimeout(() => {
      queue.show({
        id: "welcome",
        kind: "info",
        title: "Marvex is ready",
        body: "Say \"Hey Marvex\" or click the island to chat.",
        duration: 5000,
      });
    }, 1200);
    return () => clearTimeout(t);
  }, [queue]);

  const prevStatusRef = useRef<string>("idle");
  useEffect(() => {
    let cleanup: VoidFunction | undefined;
    let cardCleanup: VoidFunction | undefined;
    let approvalVoiceCleanup: VoidFunction | undefined;
    void listen("assistant-state", (event) => {
      let next: AssistantStateEvent;
      try {
        next = normalizeAssistantState(event.payload);
      } catch {
        next = idleAssistantState;
      }
      setState(next);
      // Approval cards are event-driven inside the island, not in a separate
      // window. They persist until the user decides.
      if (next.status === "needs_approval" && prevStatusRef.current !== "needs_approval") {
        void fetchPendingApprovals()
          .then((approvals) => {
            if (!approvals[0]) return;
            // Pass autoDismiss: false explicitly so the card is not auto-removed.
            queue.show(approvalCard(approvals[0]), { force: true });
          })
          .catch(() => undefined);
      }
      prevStatusRef.current = next.status;
    }).then((unlisten) => {
      cleanup = unlisten;
    });
    void listen<IslandCard>("island-card", (event) => {
      queue.show(event.payload, { force: event.payload.kind === "approval" });
    }).then((unlisten) => {
      cardCleanup = unlisten;
    });
    void listen<{ approval_id: string; decision: "approve" | "deny" | "cancel"; reason?: string }>(
      "approval-voice-decision",
      async (event) => {
        await decideApproval(event.payload.approval_id, event.payload.decision, event.payload.reason ?? "voice approval decision");
        queue.dismiss(`approval-${event.payload.approval_id}`);
      },
    ).then((unlisten) => {
      approvalVoiceCleanup = unlisten;
    });
    return () => {
      cleanup?.();
      cardCleanup?.();
      approvalVoiceCleanup?.();
    };
  }, [queue]);

  // Toggle OS-level click-through: idle pill is mostly transparent to clicks;
  // interactive (hovered / active / card) state must receive them.
  const handleMouseEnter = () => {
    setHovered(true);
    hoverEdgeTrigger(true);
  };
  const handleMouseLeave = () => {
    setHovered(false);
    hoverEdgeTrigger(false);
  };

  const audioLevel = waveformLevel(state, phase);
  const isActive = shouldShowOverlay(state);
  const statusText = displayDetail(state);
  const activeCard = cardState.active;
  const expanded = Boolean(activeCard) || isActive || hovered;
  const view = expanded ? "ring" : "idle";

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
      void setOverlaySize(next).catch(() => undefined);
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
  }, [activeCard?.id, expanded, hovered, isActive, state.status, statusText]);

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
        onClick={openChat}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        title="Open Marvex chat"
      >
        <DynamicIsland
          view={view}
          width={expanded ? 360 : 124}
          idleContent={
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, width: "100%" }}>
              <motion.span
                animate={{ opacity: [0.45, 0.9, 0.45] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
                style={{ width: 7, height: 7, borderRadius: "50%", background: "#ffe0c2", display: "block", flex: "0 0 auto" }}
              />
              <MarvexWaveform audioLevel={audioLevel} width={64} height={24} active={false} />
            </div>
          }
          ringContent={
            activeCard
              ? <IslandCardView card={activeCard} onDismiss={() => queue.dismiss(activeCard.id)} />
              : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "stretch",
                    gap: 8,
                    width: "100%",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                    <AnimatePresence mode="wait">
                      <TextShimmer text={isActive ? statusText : "Marvex"} key={isActive ? statusText : "marvex"} />
                    </AnimatePresence>
                    <span style={{ fontSize: 10, color: "rgba(255,255,255,0.45)" }}>{state.status}</span>
                  </div>
                  <MarvexWaveform
                    audioLevel={audioLevel}
                    width={320}
                    height={80}
                    active={isActive || hovered}
                  />
                </div>
              )
          }
        />
      </div>
    </div>
  );
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

function IslandCardView({ card, onDismiss }: { card: IslandCard; onDismiss: () => void }) {
  const dragStartRef = useRef<number | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const [dragY, setDragY] = useState(0);
  const approval = card.kind === "approval" ? card.payload as ApprovalSummary : null;

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    dragStartRef.current = event.clientY;
    // Capture the pointer so onPointerMove keeps firing even if the cursor
    // leaves the element boundary mid-drag.
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerUp = () => {
    if (dragY < -42) onDismiss();
    dragStartRef.current = null;
    setDragY(0);
  };

  return (
    <motion.div
      ref={cardRef}
      role="status"
      aria-live="polite"
      className="marvex-island-card"
      style={{ transform: `translateY(${dragY}px)`, touchAction: "none" }}
      onPointerDown={handlePointerDown}
      onPointerMove={(event) => {
        if (dragStartRef.current === null) return;
        setDragY(Math.min(0, event.clientY - dragStartRef.current));
      }}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      initial={{ opacity: 0, scale: 0.86, y: -12, filter: "blur(6px)" }}
      animate={{ opacity: 1, scale: 1, y: 0, filter: "blur(0px)" }}
      exit={{ opacity: 0, scale: 0.86, y: -12, filter: "blur(6px)" }}
    >
      <div className="marvex-island-card-icon">{card.kind === "approval" ? "!" : "M"}</div>
      <div className="marvex-island-card-copy">
        <div className="marvex-island-card-title">{card.title}</div>
        {card.body && <div className="marvex-island-card-body">{card.body}</div>}
      </div>
      {approval ? <ApprovalActions approval={approval} onDone={onDismiss} /> : (
        <button className="marvex-island-card-action" type="button" onClick={(event) => { event.stopPropagation(); onDismiss(); }}>Dismiss</button>
      )}
    </motion.div>
  );
}

function ApprovalActions({ approval, onDone }: { approval: ApprovalSummary; onDone: () => void }) {
  const [pending, setPending] = useState(false);
  const resumable = Boolean(approval.trace_id && approval.turn_id);
  async function decide(decision: "approve" | "deny" | "cancel") {
    if (!approval.trace_id || !approval.turn_id) return;
    setPending(true);
    try {
      await decideApproval(approval.approval_request_id, decision, `dynamic island ${decision}`);
      await resumeApprovalTurn({
        text: approval.user_visible_summary,
        traceId: approval.trace_id,
        turnId: approval.turn_id,
        approvalId: approval.approval_request_id,
        decision,
      });
      onDone();
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="marvex-island-approval-actions">
      <button disabled={pending || !resumable} type="button" onClick={(event) => { event.stopPropagation(); void decide("approve"); }}>Approve</button>
      <button disabled={pending || !resumable} type="button" onClick={(event) => { event.stopPropagation(); void decide("deny"); }}>Deny</button>
      <button disabled={pending || !resumable} type="button" onClick={(event) => { event.stopPropagation(); void decide("cancel"); }}>Cancel</button>
    </div>
  );
}

// Kept for backward compat (tests import WaveformCanvas).
export function WaveformCanvas({ state }: { state: AssistantStateEvent }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let frameCount = 0;
    let animation = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      const context = canvas?.getContext("2d");
      if (!canvas || !context) return;
      const width = canvas.width;
      const height = canvas.height;
      // Convert frame counter to radians so waveformLevel receives a proper
      // phase value — at 60fps this produces ~6.28 rad/s (one full cycle/sec).
      const phaseRad = (frameCount / 60) * (2 * Math.PI);
      const level = waveformLevel(state, phaseRad);
      context.clearRect(0, 0, width, height);
      context.strokeStyle = state.status === "needs_approval" ? "#e54d2e" : "#ffe0c2";
      context.lineWidth = 2;
      context.beginPath();
      for (let x = 0; x < width; x += 4) {
        const t = x / width;
        const carrier = Math.sin(t * Math.PI * 8 + phaseRad);
        const envelope = Math.sin(t * Math.PI);
        const y = height / 2 + carrier * envelope * Math.max(3, level * 22);
        if (x === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      }
      context.stroke();
      frameCount += 1;
      animation = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animation);
  }, [state]);

  return (
    <canvas
      className="waveform"
      width={220}
      height={34}
      ref={canvasRef}
      aria-label="Assistant audio level waveform"
    />
  );
}
