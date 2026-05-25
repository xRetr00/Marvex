import { useEffect, useRef } from "react";

export type AgentState = null | "thinking" | "listening" | "talking";

type OrbProps = {
  colors?: [string, string];
  colorsRef?: React.RefObject<[string, string]>;
  resizeDebounce?: number;
  seed?: number;
  agentState?: AgentState;
  volumeMode?: "auto" | "manual";
  manualInput?: number;
  manualOutput?: number;
  inputVolumeRef?: React.RefObject<number>;
  outputVolumeRef?: React.RefObject<number>;
  getInputVolume?: () => number;
  getOutputVolume?: () => number;
  className?: string;
};

export function Orb({
  colors = ["#CADCFC", "#A0B9D1"],
  colorsRef,
  seed = 13,
  agentState = null,
  volumeMode = "auto",
  manualInput,
  manualOutput,
  inputVolumeRef,
  outputVolumeRef,
  getInputVolume,
  getOutputVolume,
  className,
}: OrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number>(0);
  const stateRef = useRef(agentState);
  const colorsStateRef = useRef<[string, string]>(colors);
  const propsRef = useRef({
    volumeMode,
    manualInput,
    manualOutput,
    inputVolumeRef,
    outputVolumeRef,
    getInputVolume,
    getOutputVolume,
  });

  useEffect(() => {
    stateRef.current = agentState;
  }, [agentState]);

  useEffect(() => {
    colorsStateRef.current = colors;
  }, [colors]);

  useEffect(() => {
    propsRef.current = {
      volumeMode,
      manualInput,
      manualOutput,
      inputVolumeRef,
      outputVolumeRef,
      getInputVolume,
      getOutputVolume,
    };
  }, [volumeMode, manualInput, manualOutput, inputVolumeRef, outputVolumeRef, getInputVolume, getOutputVolume]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    let running = true;
    const random = splitmix32(seed);
    const offsets = Array.from({ length: 7 }, () => random() * Math.PI * 2);

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const scale = window.devicePixelRatio || 1;
      const width = Math.max(1, Math.floor(rect.width * scale));
      const height = Math.max(1, Math.floor(rect.height * scale));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
    };

    const draw = (now: number) => {
      if (!running) return;
      resize();
      const { width, height } = canvas;
      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width, height) * 0.37;
      const t = now / 1000;
      const liveColors = colorsRef?.current ?? colorsStateRef.current;
      const [colorA, colorB] = liveColors;
      const output = outputLevel(stateRef.current, propsRef.current, t);
      const input = inputLevel(stateRef.current, propsRef.current, t);

      context.clearRect(0, 0, width, height);
      context.globalCompositeOperation = "source-over";
      const core = context.createRadialGradient(cx, cy, radius * 0.05, cx, cy, radius * (0.95 + output * 0.18));
      core.addColorStop(0, "rgba(255,255,255,0.9)");
      core.addColorStop(0.28, colorA);
      core.addColorStop(0.72, colorB);
      core.addColorStop(1, "rgba(15,23,42,0.05)");
      context.fillStyle = core;
      context.beginPath();
      context.arc(cx, cy, radius * (0.94 + output * 0.08), 0, Math.PI * 2);
      context.fill();

      context.globalCompositeOperation = "screen";
      for (let i = 0; i < offsets.length; i += 1) {
        const angle = offsets[i] + t * (0.18 + i * 0.015);
        const wobble = Math.sin(t * (0.9 + i * 0.13) + offsets[i]) * radius * (0.08 + input * 0.05);
        const x = cx + Math.cos(angle) * (radius * 0.28 + wobble);
        const y = cy + Math.sin(angle * 0.87) * (radius * 0.2 + wobble);
        const blob = context.createRadialGradient(x, y, 0, x, y, radius * (0.42 + output * 0.14));
        blob.addColorStop(0, i % 2 === 0 ? colorA : colorB);
        blob.addColorStop(1, "rgba(255,255,255,0)");
        context.fillStyle = blob;
        context.beginPath();
        context.arc(x, y, radius * (0.52 + output * 0.12), 0, Math.PI * 2);
        context.fill();
      }

      context.globalCompositeOperation = "source-over";
      context.strokeStyle = `rgba(255,255,255,${0.18 + input * 0.32})`;
      context.lineWidth = Math.max(1, width * 0.007);
      context.beginPath();
      context.arc(cx, cy, radius * (0.98 + Math.sin(t * 1.6) * 0.015), 0, Math.PI * 2);
      context.stroke();

      frameRef.current = requestAnimationFrame(draw);
    };

    frameRef.current = requestAnimationFrame(draw);
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    return () => {
      running = false;
      cancelAnimationFrame(frameRef.current);
      resizeObserver.disconnect();
    };
  }, [colorsRef, seed]);

  return (
    <div className={className ?? "relative h-full w-full"}>
      <canvas ref={canvasRef} className="h-full w-full" aria-label="Marvex orb" />
    </div>
  );
}

function inputLevel(agentState: AgentState, props: OrbRuntimeProps, t: number): number {
  if (props.volumeMode === "manual") {
    return clamp01(props.manualInput ?? props.inputVolumeRef?.current ?? props.getInputVolume?.() ?? 0);
  }
  if (agentState === "listening") return clamp01(0.55 + Math.sin(t * 3.2) * 0.35);
  if (agentState === "talking") return clamp01(0.24 + Math.sin(t * 2.1) * 0.12);
  if (agentState === "thinking") return clamp01(0.32 + Math.sin(t * 1.6) * 0.1);
  return 0.08;
}

function outputLevel(agentState: AgentState, props: OrbRuntimeProps, t: number): number {
  if (props.volumeMode === "manual") {
    return clamp01(props.manualOutput ?? props.outputVolumeRef?.current ?? props.getOutputVolume?.() ?? 0);
  }
  if (agentState === "talking") return clamp01(0.72 + Math.sin(t * 3.6) * 0.22);
  if (agentState === "listening") return 0.42;
  if (agentState === "thinking") return clamp01(0.44 + Math.sin(t * 1.05 + 0.6) * 0.12);
  return 0.28;
}

type OrbRuntimeProps = Pick<
  OrbProps,
  "volumeMode" | "manualInput" | "manualOutput" | "inputVolumeRef" | "outputVolumeRef" | "getInputVolume" | "getOutputVolume"
>;

function splitmix32(a: number) {
  return function () {
    a |= 0;
    a = (a + 0x9e3779b9) | 0;
    let t = a ^ (a >>> 16);
    t = Math.imul(t, 0x21f0aaad);
    t = t ^ (t >>> 15);
    t = Math.imul(t, 0x735a2d97);
    return ((t = t ^ (t >>> 15)) >>> 0) / 4294967296;
  };
}

function clamp01(n: number) {
  if (!Number.isFinite(n)) return 0;
  return Math.min(1, Math.max(0, n));
}
