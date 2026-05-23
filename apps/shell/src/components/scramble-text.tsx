import { createElement, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*<>/\\";

interface ScrambleTextProps {
  text: string;
  className?: string;
  /** ms per character reveal step. Lower = faster resolve. */
  speed?: number;
  /** how many scramble frames a char shows before locking. */
  scrambleDepth?: number;
  /** re-run the scramble whenever `text` changes (default true). */
  retriggerOnChange?: boolean;
  as?: "span" | "div" | "h1" | "h2" | "p";
  style?: React.CSSProperties;
}

/**
 * Marvex's signature text reveal: characters tumble through random glyphs and
 * lock left-to-right into the target string. Pure rAF, no deps.
 */
export function ScrambleText({
  text,
  className,
  speed = 28,
  scrambleDepth = 6,
  retriggerOnChange = true,
  as = "span",
  style,
}: ScrambleTextProps) {
  const [display, setDisplay] = useState(text);
  const frame = useRef(0);
  const raf = useRef<number | null>(null);
  const lastText = useRef<string>("");

  useEffect(() => {
    if (!retriggerOnChange && lastText.current) {
      setDisplay(text);
      return;
    }
    lastText.current = text;
    const target = text;
    const total = target.length;
    let start: number | null = null;
    frame.current = 0;

    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced || total === 0) {
      setDisplay(target);
      return;
    }

    const step = (ts: number) => {
      if (start === null) start = ts;
      const elapsed = ts - start;
      const revealed = Math.floor(elapsed / speed);
      let out = "";
      let done = true;
      for (let i = 0; i < total; i++) {
        const ch = target[i];
        if (ch === " ") {
          out += " ";
          continue;
        }
        if (i < revealed - scrambleDepth) {
          out += ch;
        } else if (i < revealed) {
          out += GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
          done = false;
        } else {
          out += " ";
          done = false;
        }
      }
      setDisplay(out);
      if (!done) {
        raf.current = requestAnimationFrame(step);
      } else {
        setDisplay(target);
      }
    };
    raf.current = requestAnimationFrame(step);
    return () => {
      if (raf.current !== null) cancelAnimationFrame(raf.current);
    };
  }, [text, speed, scrambleDepth, retriggerOnChange]);

  return createElement(
    as,
    { className: cn("tabular-nums", className), style, "aria-label": text },
    display,
  );
}

export default ScrambleText;
