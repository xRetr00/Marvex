import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type ReactNode, useMemo, useState } from "react";

const BOUNCE_VARIANTS = {
  idle: 0.5,
  "ring-idle": 0.5,
  "timer-ring": 0.35,
  "ring-timer": 0.35,
  "timer-idle": 0.3,
  "idle-timer": 0.3,
  "idle-ring": 0.5,
} as const;

const DEFAULT_BOUNCE = 0.5;

type View = "idle" | "ring" | "timer" | "notification" | "music";

export interface DynamicIslandProps {
  className?: string;
  idleContent?: ReactNode;
  onViewChange?: (view: View) => void;
  ringContent?: ReactNode;
  timerContent?: ReactNode;
  view?: View;
  width?: number | string;
}

export default function DynamicIsland({
  view: controlledView,
  onViewChange,
  idleContent,
  ringContent,
  timerContent,
  className = "",
  width,
}: DynamicIslandProps) {
  const [internalView, setInternalView] = useState<View>("idle");
  const [variantKey, setVariantKey] = useState<string>("idle");
  const shouldReduceMotion = useReducedMotion();

  const view = controlledView ?? internalView;

  const content = useMemo(() => {
    switch (view) {
      case "ring": return ringContent ?? null;
      case "timer": return timerContent ?? null;
      default: return idleContent ?? null;
    }
  }, [view, idleContent, ringContent, timerContent]);

  const handleViewChange = (newView: View) => {
    if (view === newView) return;
    setVariantKey(`${view}-${newView}`);
    if (onViewChange) onViewChange(newView);
    else setInternalView(newView);
  };

  return (
    <motion.div
      className={`marvex-dynamic-island-pill mx-auto overflow-hidden ${className}`}
      layout
      style={{
        width: typeof width === "number" ? `${width}px` : (width ?? "min(360px, calc(100vw - 20px))"),
        minWidth: width === undefined ? undefined : typeof width === "number" ? `${width}px` : width,
        boxSizing: "border-box",
        // Near-black rather than pure #000 so the pill reads as a distinct
        // physical object floating above the desktop without a white halo.
        background: "#060606",
        borderRadius: 30,
        padding: "14px 20px",
        display: "flex",
        alignItems: "center",
        gap: 10,
        color: "#fff",
        userSelect: "none",
        // Layered shadow: tight contact shadow, mid diffuse, and outer ambient
        // so the pill has depth at every zoom level. Inner highlight creates the
        // impression of a polished edge on a dark display cutout.
        boxShadow: [
          "0 1px 2px rgba(0,0,0,0.92)",
          "0 4px 12px rgba(0,0,0,0.72)",
          "0 16px 40px rgba(0,0,0,0.48)",
          "inset 0 1px 0 rgba(255,255,255,0.06)",
          "inset 0 -1px 0 rgba(255,255,255,0.02)",
        ].join(", "),
      }}
      transition={
        shouldReduceMotion
          ? { duration: 0 }
          : {
              type: "spring" as const,
              bounce: BOUNCE_VARIANTS[variantKey as keyof typeof BOUNCE_VARIANTS] ?? DEFAULT_BOUNCE,
              // Slightly snappier than before so expand/collapse feels native.
              duration: 0.38,
            }
      }
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={view}
          style={{ width: "100%", minWidth: 0 }}
          animate={shouldReduceMotion ? { scale: 1, opacity: 1 } : { scale: 1, opacity: 1, filter: "blur(0px)", originX: 0.5, originY: 0.5, transition: { delay: 0.05 } }}
          initial={{ scale: 0.8, opacity: 0, filter: "blur(5px)", originX: 0.5, originY: 0.5 }}
          transition={{ type: "spring" as const, bounce: BOUNCE_VARIANTS[variantKey as keyof typeof BOUNCE_VARIANTS] ?? DEFAULT_BOUNCE }}
        >
          {content}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
