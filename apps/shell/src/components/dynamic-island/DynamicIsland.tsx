import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type CSSProperties, type ReactNode, useMemo, useState } from "react";
import { ISLAND_GEOMETRY } from "./geometry.generated";

// Spring bounce tuned per transition, ported from the smoothui Dynamic Island
// (UI_EXTERNAL_Helpers/components/dynamic-island.tsx). Marvex only morphs between
// two states — a compact idle pill and an expanded pill — so the view space is
// reduced from the source's idle/ring/timer/notification/music.
const BOUNCE_VARIANTS = {
  idle: 0.5,
  "idle-expanded": 0.5,
  "expanded-idle": 0.4,
} as const;

const DEFAULT_BOUNCE = 0.5;

export type IslandView = "idle" | "expanded";

export interface DynamicIslandProps {
  view: IslandView;
  idleContent?: ReactNode;
  expandedContent?: ReactNode;
  /** Explicit pill width (px or CSS length). Defaults to the generated geometry. */
  width?: number | string;
  className?: string;
}

function resolveWidth(view: IslandView, width: DynamicIslandProps["width"]): string {
  if (typeof width === "number") return `${width}px`;
  if (typeof width === "string") return width;
  // Idle hugs its content (dot + state label + mini waveform) with a minimum;
  // expanded uses the generated max width.
  return view === "expanded" ? `${ISLAND_GEOMETRY.expanded.maxWidth}px` : "max-content";
}

export default function DynamicIsland({
  view,
  idleContent,
  expandedContent,
  width,
  className = "",
}: DynamicIslandProps) {
  const shouldReduceMotion = useReducedMotion();
  const [variantKey, setVariantKey] = useState<string>("idle");

  // Track the transition so the spring bounce matches the direction of travel.
  const [prevView, setPrevView] = useState<IslandView>(view);
  if (prevView !== view) {
    setVariantKey(`${prevView}-${view}`);
    setPrevView(view);
  }

  const content = useMemo(
    () => (view === "expanded" ? expandedContent ?? null : idleContent ?? null),
    [view, idleContent, expandedContent],
  );

  const radius = view === "expanded" ? ISLAND_GEOMETRY.expanded.radius : ISLAND_GEOMETRY.idle.radius;

  const pillStyle: CSSProperties = {
    width: resolveWidth(view, width),
    minWidth: view === "idle" && width === undefined ? ISLAND_GEOMETRY.idle.minWidth : undefined,
    boxSizing: "border-box",
    // Near-black (not pure #000) so the pill reads as a physical object above the
    // desktop without a white halo.
    background: "#060606",
    borderRadius: radius,
    padding: `${ISLAND_GEOMETRY.padding.y}px ${ISLAND_GEOMETRY.padding.x}px`,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    color: "#fff",
    userSelect: "none",
    overflow: "hidden",
    // Grow downward from the top-center notch (the anchor borrowed from the
    // dynamic-island-web-main clone) instead of scaling from the middle.
    transformOrigin: "center top",
    // Inset-only: the window is clipped exactly to the pill, so any *outer* drop
    // shadow would be hard-clipped at the window edge. The real Dynamic Island is
    // a shadowless cutout; a bright top edge + faint ring give it physical depth.
    boxShadow: [
      "inset 0 1px 0 rgba(255,255,255,0.08)",
      "inset 0 0 0 1px rgba(255,255,255,0.05)",
      "inset 0 -1px 0 rgba(255,255,255,0.02)",
    ].join(", "),
  };

  const bounce = BOUNCE_VARIANTS[variantKey as keyof typeof BOUNCE_VARIANTS] ?? DEFAULT_BOUNCE;

  return (
    <motion.div
      className={`marvex-island-pill mx-auto ${className}`}
      layout
      style={pillStyle}
      transition={
        shouldReduceMotion
          ? { duration: 0 }
          : { type: "spring" as const, bounce, duration: 0.38 }
      }
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={view}
          style={{ width: "100%", minWidth: 0, display: "flex", justifyContent: "center" }}
          initial={
            shouldReduceMotion
              ? { opacity: 1 }
              : { scale: 0.85, opacity: 0, filter: "blur(5px)" }
          }
          animate={
            shouldReduceMotion
              ? { opacity: 1 }
              : { scale: 1, opacity: 1, filter: "blur(0px)", transition: { delay: 0.05 } }
          }
          exit={shouldReduceMotion ? { opacity: 0 } : { scale: 0.85, opacity: 0, filter: "blur(5px)" }}
          transition={{ type: "spring" as const, bounce }}
        >
          {content}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
