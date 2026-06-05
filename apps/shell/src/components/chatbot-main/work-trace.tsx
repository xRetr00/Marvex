import { useEffect, useState } from "react";
import {
  Brain,
  Calculator,
  CheckCircle2,
  ChevronDownIcon,
  Clock,
  FilePen,
  FileText,
  Globe,
  ListTree,
  Loader2,
  MonitorCog,
  Search,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Reasoning, ReasoningContent, ReasoningTrigger } from "@/components/ui/reasoning";
import { activityLabel, type ActivityStep } from "@/lib/activityLabels";
import { ShimmerText } from "./activity";
import { cn } from "@/lib/utils";

/** Pick a glyph for a tool/capability step from its name. */
export function iconForTool(name: string): LucideIcon {
  const n = name.toLowerCase();
  if (n.includes("search") && n.includes("web")) return Globe;
  if (n.includes("rg") || n.includes("search")) return Search;
  if (n.includes("read")) return FileText;
  if (n.includes("list")) return ListTree;
  if (n.includes("write") || n.includes("patch")) return FilePen;
  if (n.includes("web")) return Globe;
  if (n.includes("browser") || n.includes("playwright") || n.includes("browse")) return Globe;
  if (n.includes("computer")) return MonitorCog;
  if (n.includes("calc")) return Calculator;
  if (n.includes("time") || n.includes("date")) return Clock;
  return Wrench;
}

/** "8s" / "4m 12s" / "4m" */
function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

/** Live elapsed time (ticks every second) while `active`, frozen otherwise. */
function useElapsed(active: boolean, startedAt?: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);
  return startedAt != null ? Math.max(0, now - startedAt) : 0;
}

export interface WorkTraceProps {
  /** Private reasoning ("thinking"), tags already stripped. */
  thinking?: string;
  /** True while the <think> block is still open (reasoning streaming in). */
  thinkingStreaming?: boolean;
  /** Live tool-call steps for the chain of thought. */
  activity: ActivityStep[];
  /** True while the assistant turn is still streaming. */
  streaming: boolean;
  /** Epoch ms when the turn started (drives the live timer). */
  startedAt?: number;
  /** Epoch ms when the turn finished (drives "Worked for …"). */
  endedAt?: number;
}

/**
 * Unified "Working…/Worked for …" trace. Collapsed it shows just the current
 * step (shimmering while live) plus a running timer; expanded it reveals the
 * full chain of thought — the live reasoning stream and every tool step.
 */
export function WorkTrace({
  thinking,
  thinkingStreaming = false,
  activity,
  streaming,
  startedAt,
  endedAt,
}: WorkTraceProps) {
  const working = streaming;
  const hasStart = startedAt != null;
  const liveElapsed = useElapsed(working, startedAt);
  const duration = working
    ? liveElapsed
    : hasStart && endedAt != null
      ? Math.max(0, endedAt - startedAt)
      : liveElapsed;

  const activeStep = [...activity].reverse().find((step) => step.active);
  const currentLabel = activeStep
    ? activityLabel(activeStep)
    : thinkingStreaming
      ? "Thinking"
      : "Working";

  const hasDetail = Boolean(thinking) || activity.length > 0;
  const openByDefault = Boolean(thinking) || (streaming && thinkingStreaming);

  return (
    <Collapsible
      defaultOpen={openByDefault}
      className="not-prose w-full max-w-[min(100%,72ch)] overflow-hidden rounded-xl border border-border/45 bg-card/35 shadow-[var(--shadow-card)] backdrop-blur-sm"
    >
      <CollapsibleTrigger
        className="group flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-muted-foreground transition-colors hover:text-foreground"
        disabled={!hasDetail}
      >
        {working ? (
          <Loader2 className="size-3.5 shrink-0 animate-spin text-chart-2" />
        ) : (
          <CheckCircle2 className="size-3.5 shrink-0 text-chart-2" />
        )}
        <span className="min-w-0 flex-1 truncate">
          {working ? (
            <ShimmerText>{currentLabel}</ShimmerText>
          ) : (
            <span>{hasStart ? `Worked for ${formatDuration(duration)}` : "Worked"}</span>
          )}
        </span>
        {working && hasStart ? (
          <span className="shrink-0 tabular-nums text-[11px] text-muted-foreground/70">
            {formatDuration(duration)}
          </span>
        ) : null}
        {hasDetail ? (
          <ChevronDownIcon className="size-4 shrink-0 transition-transform group-data-[state=open]:rotate-180" />
        ) : null}
      </CollapsibleTrigger>

      {hasDetail ? (
        <CollapsibleContent className="data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0">
          <div className="space-y-2 border-t border-border/40 px-3 py-2.5">
            {thinking ? (
              <Reasoning isStreaming={streaming && thinkingStreaming} defaultOpen={Boolean(thinking)}>
                <ReasoningTrigger />
                <ReasoningContent>{thinking}</ReasoningContent>
              </Reasoning>
            ) : null}
            {activity.length > 0 ? (
              <div className="space-y-1.5">
                {activity.map((step) => {
                  const Icon = iconForTool(step.name);
                  return (
                    <div
                      key={step.id}
                      className={cn(
                        "flex items-center gap-2 text-xs",
                        step.active ? "text-foreground" : "text-muted-foreground",
                      )}
                    >
                      {step.active ? (
                        <Loader2 className="size-3.5 shrink-0 animate-spin text-chart-2" />
                      ) : (
                        <Icon className="size-3.5 shrink-0 text-chart-2" />
                      )}
                      {step.active ? (
                        <ShimmerText>{activityLabel(step)}</ShimmerText>
                      ) : (
                        <span className="truncate">{activityLabel(step)}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        </CollapsibleContent>
      ) : null}
    </Collapsible>
  );
}
