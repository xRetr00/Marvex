import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import AnimatedProgressBar from "@/components/animated-progress-bar";
import { fetchDeps, installDep, type Dep } from "@/lib/depsClient";
import { getBackendHealth, getSetupStatus, startSetup } from "@/lib/shellCommands";
import { markSetupDone } from "@/lib/modeStore";
import { ScrambleText } from "@/components/scramble-text";

/** Friendly text for the first-run runtime (uv venv) bootstrap phases. */
const RUNTIME_PHASE_TEXT: Record<string, string> = {
  "creating environment": "Creating the Marvex runtime environment...",
  "installing packages": "Installing the Marvex runtime (first launch only)...",
};

function isFailedPhase(phase: string): boolean {
  return (
    phase.endsWith("_failed") ||
    phase.endsWith("_incomplete") ||
    phase === "uv_unavailable" ||
    phase === "wheelhouse_missing"
  );
}

/**
 * On first launch the Rust supervisor builds a real Python venv with uv before
 * any service can answer. Wait for that "runtime" phase to reach ready/dev so
 * the deps check below can actually reach Core. Auto-retries once on failure.
 * Returns the final phase string.
 */
async function waitForRuntimeReady(setText: (text: string) => void): Promise<string> {
  let retried = false;
  for (let attempt = 0; attempt < 600; attempt++) {
    let phase = "ready";
    try {
      phase = (await getSetupStatus()).runtime_phase;
    } catch {
      return "ready"; // not running under Tauri (web/dev) — proceed
    }
    if (phase === "ready" || phase === "dev") return phase;
    if (isFailedPhase(phase)) {
      if (!retried) {
        retried = true;
        setText("Retrying runtime setup...");
        try { await startSetup(); } catch { /* ignore */ }
        await new Promise((resolve) => setTimeout(resolve, 2000));
        continue;
      }
      return phase;
    }
    setText(RUNTIME_PHASE_TEXT[phase] ?? "Preparing Marvex...");
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return "ready";
}

async function waitForBackendDeps(setText: (text: string) => void) {
  for (let attempt = 0; attempt < 180; attempt++) {
    try {
      const health = await getBackendHealth();
      if (health.reachable) {
        return await fetchDeps();
      }
      setText("Waiting for Core to accept connections...");
    } catch {
      setText("Waiting for Control Plane...");
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("backend_not_reachable_after_runtime_ready");
}

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
  const [bootText, setBootText] = useState<string | null>(null);
  const didRun = useRef(false);

  useEffect(() => {
    if (didRun.current) return;
    didRun.current = true;

    void (async () => {
      try {
        // First launch: wait for the uv venv bootstrap before reaching Core.
        const runtime = await waitForRuntimeReady(setBootText);
        if (isFailedPhase(runtime)) {
          setError("Runtime setup failed. Restart Marvex or reinstall the packaged runtime.");
          setPhase("error");
          return;
        }
        setBootText(null);
        const depsData = await waitForBackendDeps(setBootText);
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

        const finalStatus = await fetchDeps();
        if (finalStatus.deps.some((dep) => !dep.installed)) {
          setError("Runtime setup failed. Restart Marvex or reinstall the packaged runtime.");
          setPhase("error");
          return;
        }
        setPhase("done");
        setTimeout(() => { markSetupDone(); onComplete(); }, 1200);
      } catch (err) {
        setError("Backend not reachable. Runtime setup is still pending.");
        setPhase("error");
      }
    })();
  }, [onComplete]);

  return (
    <div className="fixed inset-0 flex items-center justify-center" style={{ background: "var(--background)", color: "var(--foreground)" }}>
      <div className="w-full max-w-md px-8 space-y-8">
        {/* Logo */}
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-center gap-3">
          <img src="/assets/Marvex_WordMark_NoBackground.png" alt="Marvex" className="h-10 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          <ScrambleText text="Setup" className="text-2xl font-bold tracking-tight" style={{ color: "var(--primary)" }} />
        </motion.div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="space-y-2">
          <p className="text-sm text-center" style={{ color: "var(--muted-foreground)" }}>
            {phase === "loading" && (bootText ?? "Checking dependencies...")}
            {phase === "installing" && "Installing required components..."}
            {phase === "done" && "Setup complete. Starting Marvex..."}
            {phase === "error" && (error ?? "Something went wrong.")}
          </p>
          <AnimatedProgressBar value={progress} color="var(--primary)" className="rounded-full" />
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
