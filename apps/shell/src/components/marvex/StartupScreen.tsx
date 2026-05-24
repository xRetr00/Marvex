import { RefreshCw } from "lucide-react";
import { FAILED_PHASES, serviceOk, type BackendStatus } from "@/lib/backendStatus";
import { AppleHelloEnglishEffect } from "@/components/apple-hello-effect";
import { ScrambleText } from "@/components/scramble-text";
import { Loader } from "@/components/loader";
import { BackgroundPlus } from "@/components/ui/background-plus";
import { Button } from "@/components/ui/button";

/**
 * Shared startup/waiting screen: plays the Apple-hello and shows live backend
 * bring-up (runtime phase + per-service status), with a retry on setup failure.
 * Used by both the chat window and the Control Plane loader.
 */
export function StartupScreen({
  backend,
  title = "I am Marvex",
  onHelloDone,
  onRetry,
}: {
  backend: BackendStatus | null;
  title?: string;
  onHelloDone?: () => void;
  onRetry?: () => void;
}) {
  const phase = backend?.phase ?? "starting";
  const failed = FAILED_PHASES.has(phase);
  const services = backend?.services ?? {};
  const serviceNames = Object.keys(services).filter((n) => n !== "runtime");
  return (
    <div className="flex flex-col items-center justify-center h-screen gap-6 relative" style={{ background: "var(--background)", color: "var(--foreground)" }}>
      <BackgroundPlus plusColor="#ffe0c2" plusSize={56} fade className="pointer-events-none opacity-25" />
      <AppleHelloEnglishEffect className="h-16" style={{ color: "var(--primary)" }} speed={1.1} onAnimationComplete={onHelloDone} />
      <ScrambleText text={title} className="text-sm tracking-[0.35em] uppercase" style={{ color: "var(--muted-foreground)" }} speed={45} />

      <div style={{ width: 360, maxWidth: "82vw", display: "flex", flexDirection: "column", gap: 8, marginTop: 6 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, color: "var(--muted-foreground)", fontSize: 12 }}>
          {!backend?.ready && !failed && <Loader variant="circular" size="sm" />}
          <span>{failed ? "Setup needed" : backend?.ready ? "Ready" : `Bringing up backend… (${phase})`}</span>
        </div>
        {serviceNames.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 6 }}>
            {serviceNames.map((name) => {
              const ok = serviceOk(services[name]);
              return (
                <div key={name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "6px 9px", borderRadius: 8, background: "var(--secondary)", border: "1px solid var(--border)", fontSize: 11 }}>
                  <span style={{ textTransform: "capitalize" }}>{name.replace(/_/g, " ")}</span>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: ok ? "#34d399" : "#f59e0b" }} />
                </div>
              );
            })}
          </div>
        )}
        {failed && onRetry && (
          <Button size="sm" variant="outline" className="mx-auto mt-2" onClick={onRetry}><RefreshCw size={14} className="mr-1" /> Retry setup</Button>
        )}
      </div>
    </div>
  );
}
