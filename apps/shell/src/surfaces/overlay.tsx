import { useEffect, useRef, useState } from "react";
import { listen } from "../lib/tauriBridge";
import { displayDetail, idleAssistantState, normalizeAssistantState, shouldShowOverlay, statusLabel, type AssistantStateEvent, waveformLevel } from "../lib/assistantState";
import { setOverlayClickThrough } from "../lib/shellCommands";

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
    }).then((unlisten) => { cleanup = unlisten; });
    return () => cleanup?.();
  }, []);

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const rect = interactiveRef.current?.getBoundingClientRect();
      const overInteractive = Boolean(rect && event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom);
      void setOverlayClickThrough(!overInteractive);
    };
    window.addEventListener("mousemove", onMove);
    void setOverlayClickThrough(true);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  if (!shouldShowOverlay(state)) return null;

  return (
    <div className="overlay-shell" ref={interactiveRef}>
      <div className="status-pill">
        <span className={`status-dot status-${state.status}`} />
        <span>{statusLabel(state.status)}</span>
      </div>
      <div className="overlay-detail">{displayDetail(state)}</div>
      <WaveformCanvas state={state} />
    </div>
  );
}

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
      context.strokeStyle = state.status === "needs_approval" ? "#f97316" : "#38bdf8";
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

  return <canvas className="waveform" width={220} height={34} ref={canvasRef} aria-label="Assistant audio level waveform" />;
}
