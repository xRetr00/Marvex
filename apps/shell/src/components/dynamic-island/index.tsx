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
}

export default function DynamicIsland({
  view: controlledView,
  onViewChange,
  idleContent,
  ringContent,
  timerContent,
  className = "",
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
      className={`marvex-dynamic-island-pill mx-auto w-fit min-w-[100px] overflow-hidden rounded-full bg-black ${className}`}
      layout
      style={{ borderRadius: 32 }}
      transition={
        shouldReduceMotion
          ? { duration: 0 }
          : {
              type: "spring" as const,
              bounce: BOUNCE_VARIANTS[variantKey as keyof typeof BOUNCE_VARIANTS] ?? DEFAULT_BOUNCE,
              duration: 0.25,
            }
      }
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={view}
          animate={shouldReduceMotion ? { scale: 1, opacity: 1 } : { scale: 1, opacity: 1, filter: "blur(0px)", originX: 0.5, originY: 0.5, transition: { delay: 0.05 } }}
          initial={{ scale: 0.9, opacity: 0, filter: "blur(5px)", originX: 0.5, originY: 0.5 }}
          transition={{ type: "spring" as const, bounce: BOUNCE_VARIANTS[variantKey as keyof typeof BOUNCE_VARIANTS] ?? DEFAULT_BOUNCE }}
        >
          {content}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
