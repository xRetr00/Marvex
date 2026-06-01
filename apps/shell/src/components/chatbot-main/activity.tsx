import { Brain, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function ShimmerText({ children, className }: { children: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-block bg-[linear-gradient(90deg,var(--muted-foreground),var(--foreground),var(--muted-foreground))] bg-[length:200%_100%] bg-clip-text text-transparent",
        "[animation:marvex-shimmer_1.7s_linear_infinite]",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function AssistantActivity({ label }: { label: string }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/80 px-3 py-1.5 text-sm text-muted-foreground shadow-[var(--shadow-card)] backdrop-blur-lg">
      <Loader2 className="size-3.5 animate-spin text-chart-2" />
      <ShimmerText>{label}</ShimmerText>
    </div>
  );
}

export function ReasoningStageList({ stages }: { stages: Array<{ stage_name: string; status: string }> }) {
  return (
    <div className="mt-2 space-y-2 rounded-lg border border-border/60 bg-muted/25 p-3">
      {stages.map((stage, index) => {
        const active = ["in_progress", "running", "active", "started"].includes(stage.status);
        const complete = ["completed", "succeeded", "ok", "done"].includes(stage.status);
        const Icon = active ? Loader2 : complete ? CheckCircle2 : Circle;
        return (
          <div key={`${stage.stage_name}-${index}`} className="flex items-center gap-2 text-xs text-muted-foreground">
            <Icon className={cn("size-3.5", active && "animate-spin text-chart-2", complete && "text-chart-2")} />
            {active ? (
              <ShimmerText>{stage.stage_name.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</ShimmerText>
            ) : (
              <span>{stage.stage_name.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ReasoningHeader({ open }: { open: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <Brain className="size-3.5 text-chart-2" />
      <span>{open ? "Hide activity" : "View activity"}</span>
    </span>
  );
}
