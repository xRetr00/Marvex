import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ExpandableCardProps {
  title: string;
  src: string;
  description: string;
  children?: React.ReactNode;
  className?: string;
  classNameExpanded?: string;
  [key: string]: unknown;
}

export function ExpandableCard({ title, src, description, children, className, classNameExpanded, ...props }: ExpandableCardProps) {
  const [active, setActive] = React.useState(false);
  const cardRef = React.useRef<HTMLDivElement>(null);
  const id = React.useId();

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setActive(false); };
    const handleClickOutside = (event: MouseEvent | TouchEvent) => {
      if (cardRef.current && !cardRef.current.contains(event.target as Node)) setActive(false);
    };
    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, []);

  return (
    <>
      <AnimatePresence>
        {active && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-white/50 dark:bg-black/50 backdrop-blur-md h-full w-full z-10" />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {active && (
          <div className="fixed inset-0 grid place-items-center z-[100]">
            <motion.div layoutId={`card-${title}-${id}`} ref={cardRef}
              className={cn("w-full max-w-[850px] h-full flex flex-col overflow-auto rounded-t-3xl bg-zinc-50 dark:bg-zinc-950 relative", classNameExpanded)}>
              <motion.div layoutId={`image-${title}-${id}`}>
                <img src={src} alt={title} className="w-full h-80 object-cover" />
              </motion.div>
              <div className="flex justify-between items-start p-8">
                <div>
                  <motion.p layoutId={`description-${description}-${id}`} className="text-zinc-500 text-lg">{description}</motion.p>
                  <motion.h3 layoutId={`title-${title}-${id}`} className="font-semibold text-black dark:text-white text-4xl mt-0.5">{title}</motion.h3>
                </div>
                <motion.button aria-label="Close card" layoutId={`button-${title}-${id}`}
                  className="h-10 w-10 flex items-center justify-center rounded-full bg-zinc-50 dark:bg-zinc-950 border"
                  onClick={() => setActive(false)}>
                  <motion.div animate={{ rotate: active ? 45 : 0 }} transition={{ duration: 0.4 }}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14" /><path d="M12 5v14" />
                    </svg>
                  </motion.div>
                </motion.button>
              </div>
              <div className="px-8 pb-10">{children}</div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
      <motion.div layoutId={`card-${title}-${id}`} onClick={() => setActive(true)}
        className={cn("p-3 flex flex-col justify-between items-center bg-zinc-50 dark:bg-zinc-950 rounded-2xl cursor-pointer border", className)}>
        <div className="flex gap-4 flex-col">
          <motion.div layoutId={`image-${title}-${id}`}>
            <img src={src} alt={title} className="w-64 h-56 rounded-lg object-cover" />
          </motion.div>
          <div className="flex justify-between items-center">
            <div className="flex flex-col">
              <motion.p layoutId={`description-${description}-${id}`} className="text-zinc-500 text-sm font-medium">{description}</motion.p>
              <motion.h3 layoutId={`title-${title}-${id}`} className="text-black dark:text-white font-semibold">{title}</motion.h3>
            </div>
            <motion.button aria-label="Open card" layoutId={`button-${title}-${id}`} className="h-8 w-8 flex items-center justify-center rounded-full border">
              <motion.div animate={{ rotate: active ? 45 : 0 }} transition={{ duration: 0.4 }}>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14" /><path d="M12 5v14" />
                </svg>
              </motion.div>
            </motion.button>
          </div>
        </div>
      </motion.div>
    </>
  );
}
