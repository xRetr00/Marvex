import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import AnimatedProgressBar from "@/components/animated-progress-bar";
import { fetchDeps, installDep, type Dep } from "@/lib/depsClient";
import { markSetupDone } from "@/lib/modeStore";

interface SetupProps {
  onComplete: () => void;
}

interface DepInstallState {
  dep: Dep;
  status: "pending" | "installing" | "installed" | "error";
  detail?: string;
}

export function SetupPage({ onComplete }: SetupProps) {
  const [deps, setDeps] = useState<DepInstallState[]>([]);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState<"loading" | "installing" | "done" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const didRun = useRef(false);

  useEffect(() => {
    if (didRun.current) return;
    didRun.current = true;

    void (async () => {
      try {
        const depsData = await fetchDeps();
        const missing = depsData.deps.filter((d) => !d.installed);

        if (missing.length === 0) {
          setProgress(100);
          setPhase("done");
          setTimeout(() => { markSetupDone(); onComplete(); }, 800);
          return;
        }

        const states: DepInstallState[] = missing.map((dep) => ({ dep, status: "pending" as const }));
        setDeps(states);
        setPhase("installing");

        for (let i = 0; i < states.length; i++) {
          setDeps((prev) => prev.map((s, idx) => idx === i ? { ...s, status: "installing" } : s));
          try {
            const result = await installDep(states[i].dep.id);
            setDeps((prev) =>
              prev.map((s, idx) => idx === i ? { ...s, status: result.status === "installed" ? "installed" : "error", detail: result.detail } : s),
            );
          } catch {
            setDeps((prev) => prev.map((s, idx) => idx === i ? { ...s, status: "error", detail: "Install failed" } : s));
          }
          setProgress(Math.round(((i + 1) / states.length) * 100));
        }

        setPhase("done");
        setTimeout(() => { markSetupDone(); onComplete(); }, 1200);
      } catch (err) {
        // Backend not available — skip setup
        setError("Backend not reachable. Starting anyway.");
        setPhase("error");
        setTimeout(() => { markSetupDone(); onComplete(); }, 1500);
      }
    })();
  }, [onComplete]);

  return (
    <div className="fixed inset-0 bg-[#08151a] flex items-center justify-center">
      <div className="w-full max-w-md px-8 space-y-8">
        {/* Logo */}
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-center gap-3">
          <img src="/assets/Marvex_WordMark_NoBackground.png" alt="Marvex" className="h-10 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          <span className="text-white text-2xl font-bold tracking-tight">Marvex</span>
        </motion.div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="space-y-2">
          <p className="text-white/60 text-sm text-center">
            {phase === "loading" && "Checking dependencies..."}
            {phase === "installing" && "Installing required components..."}
            {phase === "done" && "Setup complete. Starting Marvex..."}
            {phase === "error" && (error ?? "Something went wrong.")}
          </p>
          <AnimatedProgressBar value={progress} color="#38bdf8" className="rounded-full" />
        </motion.div>

        <AnimatePresence>
          {deps.length > 0 && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="space-y-2 overflow-hidden">
              {deps.map((s) => (
                <motion.div key={s.dep.id} layout className="flex items-center gap-3 bg-white/5 rounded-lg px-4 py-2">
                  <div className="flex-shrink-0">
                    {s.status === "installed" && <CheckCircle2 className="size-4 text-emerald-400" />}
                    {s.status === "error" && <AlertCircle className="size-4 text-red-400" />}
                    {(s.status === "pending" || s.status === "installing") && (
                      <Loader2 className={`size-4 text-blue-400 ${s.status === "installing" ? "animate-spin" : "opacity-40"}`} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-medium truncate">{s.dep.label}</p>
                    <p className="text-white/40 text-xs">{s.dep.group}</p>
                  </div>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${s.status === "installed" ? "bg-emerald-500/20 text-emerald-400" : s.status === "error" ? "bg-red-500/20 text-red-400" : s.status === "installing" ? "bg-blue-500/20 text-blue-400" : "bg-white/10 text-white/40"}`}>
                    {s.status}
                  </span>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
