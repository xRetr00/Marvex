import { useEffect, useRef, useState } from "react";
import { listen } from "../lib/tauriBridge";
import {
  displayDetail,
  idleAssistantState,
  normalizeAssistantState,
  shouldShowOverlay,
  type AssistantStateEvent,
  waveformLevel,
} from "../lib/assistantState";
import { setOverlayClickThrough, showChat } from "../lib/shellCommands";
import { makeHoverEdgeTrigger } from "../lib/overlayHover";
import { persistMode } from "../lib/modeStore";
import DynamicIsland from "@/components/dynamic-island";
import { MarvexWaveform } from "@/components/waveform-shader/MarvexWaveform";
import { AnimatePresence, motion } from "framer-motion";

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

export function OverlaySurface() {
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const [hovered, setHovered] = useState(false);
  const islandRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cleanup: VoidFunction | undefined;
    void listen("assistant-state", (event) => {
      try {
        setState(normalizeAssistantState(event.payload));
      } catch {
        setState(idleAssistantState);
      }
    }).then((unlisten) => {
      cleanup = unlisten;
    });
    return () => cleanup?.();
  }, []);

  // Click-through everywhere except directly over the island. The bounds check
  // is throttled to one rAF per frame and the click-through IPC call is
  // edge-triggered (fires only on enter/leave), so moving the mouse no longer
  // floods the Tauri bridge and freezes the app.
  useEffect(() => {
    const trigger = makeHoverEdgeTrigger((over) => void setOverlayClickThrough(!over));
    let frame = 0;
    const onMove = (event: MouseEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const rect = islandRef.current?.getBoundingClientRect();
        const over = Boolean(
          rect &&
            event.clientX >= rect.left &&
            event.clientX <= rect.right &&
            event.clientY >= rect.top &&
            event.clientY <= rect.bottom,
        );
        setHovered(over);
        trigger(over);
      });
    };
    window.addEventListener("mousemove", onMove);
    void setOverlayClickThrough(true);
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  const audioLevel = waveformLevel(state);
  const isActive = shouldShowOverlay(state);
  const statusText = displayDetail(state);
  const expanded = isActive || hovered;
  const view = expanded ? "ring" : "idle";

  const openChat = () => {
    persistMode("chat");
    void showChat().catch(() => undefined);
  };

  return (
    <div className="overlay-shell">
      <div
        ref={islandRef}
        style={{ width: "fit-content", cursor: "pointer" }}
        onClick={openChat}
        title="Open Marvex chat"
      >
        <DynamicIsland
          view={view}
          idleContent={
            <div style={{ padding: "7px 12px", display: "flex", alignItems: "center", gap: 8 }}>
              <motion.span
                animate={{ opacity: [0.45, 0.9, 0.45] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
                style={{ width: 8, height: 8, borderRadius: "50%", background: "#ffe0c2", display: "block" }}
              />
              <MarvexWaveform audioLevel={0.12} width={36} height={16} active={false} />
              <AnimatePresence mode="wait">
                <TextShimmer text={statusText} key={statusText} />
              </AnimatePresence>
            </div>
          }
          ringContent={
            <div
              style={{
                display: "flex",
                flexDirection: "row",
                alignItems: "center",
                gap: 10,
                padding: "7px 14px 7px 12px",
              }}
            >
              {/* Waveform always on the LEFT. */}
              <MarvexWaveform audioLevel={isActive ? audioLevel : 0.18} width={isActive ? 120 : 64} height={22} active={isActive || hovered} />
              <AnimatePresence mode="wait">
                <TextShimmer text={isActive ? statusText : "Marvex"} key={isActive ? statusText : "marvex"} />
              </AnimatePresence>
            </div>
          }
        />
      </div>
    </div>
  );
}

// Kept for backward compat (tests import WaveformCanvas).
export function WaveformCanvas({ state }: { state: AssistantStateEvent }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let frame = 0;
    let animation = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      const context = canvas?.getContext("2d");
      if (!canvas || !context) return;
      const width = canvas.width;
      const height = canvas.height;
      const level = waveformLevel(state, frame / 10);
      context.clearRect(0, 0, width, height);
      context.strokeStyle = state.status === "needs_approval" ? "#e54d2e" : "#ffe0c2";
      context.lineWidth = 2;
      context.beginPath();
      for (let x = 0; x < width; x += 4) {
        const t = x / width;
        const carrier = Math.sin(t * Math.PI * 8 + frame / 7);
        const envelope = Math.sin(t * Math.PI);
        const y = height / 2 + carrier * envelope * Math.max(3, level * 22);
        if (x === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      }
      context.stroke();
      frame += 1;
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
