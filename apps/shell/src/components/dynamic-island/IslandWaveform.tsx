import { MarvexWaveform } from "../waveform-shader/MarvexWaveform";
import { ISLAND_GEOMETRY } from "./geometry.generated";

export interface IslandWaveformProps {
  /** "compact" sizes the canvas for the idle pill; "expanded" for the open pill. */
  variant: "compact" | "expanded";
  /** Assistant-state amplitude (0..1); smoothed inside MarvexWaveform. */
  audioLevel: number;
  /** When false, paints a single frame then idles the GPU. */
  active?: boolean;
}

// Picks the right waveform canvas size from the generated geometry so the GLSL
// shader keeps its intended aspect ratio in both the compact and expanded pill.
export function IslandWaveform({ variant, audioLevel, active = true }: IslandWaveformProps) {
  const box = variant === "expanded" ? ISLAND_GEOMETRY.waveform.expanded : ISLAND_GEOMETRY.waveform.compact;
  return <MarvexWaveform audioLevel={audioLevel} width={box.width} height={box.height} active={active} />;
}
