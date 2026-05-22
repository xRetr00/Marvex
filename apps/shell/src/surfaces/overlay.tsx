import { useEffect, useRef, useState } from "react";
import { listen } from "../lib/tauriBridge";
import {
  displayDetail,
  idleAssistantState,
  normalizeAssistantState,
  shouldShowOverlay,
  statusLabel,
  type AssistantStateEvent,
  waveformLevel,
} from "../lib/assistantState";
import { setOverlayClickThrough } from "../lib/shellCommands";
import DynamicIsland from "@/components/dynamic-island";
import { MarvexWaveform } from "@/components/waveform-shader/MarvexWaveform";
import { AnimatePresence, motion } from "framer-motion";

// Inject shimmer keyframes once at module load — avoids a <style> tag on every render
if (typeof document !== "undefined" && !document.getElementById("marvex-shimmer-style")) {
  const style = document.createElement("style");
  style.id = "marvex-shimmer-style";
  style.textContent = `@keyframes shimmer{0%{background-position:0% center}100%{background-position:200% center}}`;
  document.head.appendChild(style);
}

const SHIMMER_STYLE: React.CSSProperties = {
  background: "linear-gradient(90deg, #38bdf8 0%, #ffffff 40%, #38bdf8 80%)",
  backgroundSize: "200% auto",
  WebkitBackgroundClip: "text",
  WebkitTextFillColor: "transparent",
  backgroundClip: "text",
  animation: "shimmer 2s linear infinite",
  fontSize: "0.75rem",
  fontWeight: 500,
  letterSpacing: "0.03em",
};

function TextShimmer({ text }: { text: string }) {
  return (
    <motion.span
      key={text}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      style={SHIMMER_STYLE}
    >
      {text}
    </motion.span>
  );
}

export function OverlaySurface() {
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const interactiveRef = useRef<HTMLDivElement | null>(null);

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

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const rect = interactiveRef.current?.getBoundingClientRect();
      const overInteractive = Boolean(
        rect &&
          event.clientX >= rect.left &&
          event.clientX <= rect.right &&
          event.clientY >= rect.top &&
          event.clientY <= rect.bottom,
      );
      void setOverlayClickThrough(!overInteractive);
    };
    window.addEventListener("mousemove", onMove);
    void setOverlayClickThrough(true);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  const audioLevel = waveformLevel(state);
  const isActive = shouldShowOverlay(state);
  const statusText = displayDetail(state);

  const dynamicIslandView = isActive ? "ring" : "idle";

  return (
    <div className="overlay-shell" ref={interactiveRef}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "8px",
          padding: "12px",
        }}
      >
        <DynamicIsland
          view={dynamicIslandView}
          idleContent={
            <div style={{ padding: "8px 16px", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#38bdf8", opacity: 0.6 }} />
            </div>
          }
          ringContent={
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "6px",
                padding: "8px 16px",
                width: "100%",
              }}
            >
              <MarvexWaveform audioLevel={audioLevel} width={200} height={32} />
              <AnimatePresence mode="wait">
                <TextShimmer text={statusText} key={statusText} />
              </AnimatePresence>
            </div>
          }
        />

        {isActive && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            style={{
              color: "rgba(255,255,255,0.5)",
              fontSize: "0.65rem",
              textAlign: "center",
            }}
          >
            {statusLabel(state.status)}
          </motion.div>
        )}
      </div>
    </div>
  );
}

// Keep WaveformCanvas export for backward compat (tests may import it)
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
      context.strokeStyle =
        state.status === "needs_approval" ? "#f97316" : "#38bdf8";
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
