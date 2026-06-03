import { lazy, Suspense, useMemo } from "react";
import { parseRichResponse, directivesToBlocks, type RichBlock } from "@/lib/richContent";
import type { TurnStage, UiDirective } from "@/lib/localTurn";
import {
  ChainOfThought,
  ChainOfThoughtHeader,
  ChainOfThoughtContent,
  ChainOfThoughtStep,
} from "@/components/chain-of-thought";
import { ShimmerText } from "@/components/chatbot-main/activity";
import { WorkTrace } from "@/components/chatbot-main/work-trace";
import { splitReasoning } from "@/lib/reasoning";
import { type ActivityStep } from "@/lib/activityLabels";
import { InlineCitation } from "@/components/chatbot-main/inline-citation";
import ProductCard from "@/components/product-card";
import { ExpandableCard } from "@/components/expandable-card";
import AgentPlan from "@/components/agent-plan";
import { AlertBadge } from "@/components/alert-badge";
import type { CitationRef } from "@/lib/localTurn";

const ChatbotMarkdown = lazy(() => import("@/components/chatbot-main/markdown").then((module) => ({ default: module.ChatbotMarkdown })));

function stageStatus(status: string): "complete" | "active" | "pending" {
  if (["completed", "succeeded", "ok", "done"].includes(status)) return "complete";
  if (["in_progress", "running", "active", "started"].includes(status)) return "active";
  return "pending";
}

function prettyStage(name: string): string {
  return name.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function citationNumber(id: string): string {
  return id.replace(/^web\.evidence\./i, "").replace(/^memory\.evidence\./i, "");
}

function citationByMarker(citations: CitationRef[]): Map<string, CitationRef> {
  const map = new Map<string, CitationRef>();
  citations.forEach((citation) => {
    map.set(citation.id, citation);
    map.set(citationNumber(citation.id), citation);
  });
  return map;
}

function MarkdownWithCitations({ text, citations }: { text: string; citations: CitationRef[] }) {
  const lookup = citationByMarker(citations);
  const parts = text.split(/(\[(?:web|memory)\.evidence\.[^\]]+\]|\[citation\s+\d+\])/gi);
  return (
    <div className="space-y-2">
      {parts.map((part, index) => {
        const evidence = part.match(/^\[((?:web|memory)\.evidence\.[^\]]+)\]$/i)?.[1];
        const numbered = part.match(/^\[citation\s+(\d+)\]$/i)?.[1];
        const citation = evidence ? lookup.get(evidence) : numbered ? lookup.get(numbered) : undefined;
        if (evidence || numbered) {
          const number = Number(citationNumber(evidence || numbered || "")) || Number(numbered) || index;
          return <InlineCitation key={`${part}-${index}`} index={number} citation={citation} />;
        }
        if (!part) return null;
        return (
          <Suspense key={index} fallback={<span className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/88">{part}</span>}>
            <ChatbotMarkdown content={part} />
          </Suspense>
        );
      })}
    </div>
  );
}

function BlockView({ block, citations }: { block: RichBlock; citations: CitationRef[] }) {
  switch (block.type) {
    case "text":
      return (
        <Suspense fallback={<p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/88">{block.text}</p>}>
          <MarkdownWithCitations text={block.text} citations={citations} />
        </Suspense>
      );
    case "info":
      return (
        <div className="rounded-xl border border-border bg-card/60 p-4">
          {block.title && <h4 className="mb-1 text-sm font-semibold text-foreground">{block.title}</h4>}
          {block.body && <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{block.body}</p>}
        </div>
      );
    case "products":
      return (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {block.products.map((p, i) => (
            <ProductCard
              key={`${p.title}-${i}`}
              image={p.image}
              title={p.title}
              price={p.price}
              originalPrice={p.originalPrice}
              currency={p.currency}
              rating={p.rating}
              badge={p.badge}
            />
          ))}
        </div>
      );
    case "image":
      return (
        <ExpandableCard title={block.title} src={block.src} description={block.description || "Image"}>
          {block.description ? <p className="text-sm text-zinc-400">{block.description}</p> : null}
        </ExpandableCard>
      );
    case "plan": {
      const tasks = block.steps.map((s, i) => ({
        id: s.id,
        title: s.title,
        description: "",
        status: i === 0 ? "in-progress" : "pending",
        priority: "medium",
        level: 0,
        dependencies: [] as string[],
        subtasks: [] as never[],
      }));
      return (
        <div className="overflow-hidden rounded-xl border border-border">
          <AgentPlan tasks={tasks} />
        </div>
      );
    }
    case "alert":
      return <AlertBadge variant="info" label={block.label} />;
    default:
      return null;
  }
}

function sanitizeAssistantText(text: string): string {
  return text
    .split(/\n+/)
    .filter((line) => !/approval_request_id\s*=/.test(line))
    .filter((line) => !/^Approval required before continuing\./i.test(line.trim()))
    .map((line) => line.replace(/\[web\.evidence\.(\d+)\]/gi, "[citation $1]"))
    .join("\n")
    .trim();
}

export interface RichMessageProps {
  text: string;
  stages?: TurnStage[];
  citations?: CitationRef[];
  /** Backend model-driven directives; when present they drive rendering (not keyword heuristics). */
  directives?: UiDirective[];
  /** True while the assistant turn is still streaming (drives live thinking). */
  streaming?: boolean;
  /** Live tool-call steps for the unified Chain-of-Thought feed. */
  activity?: ActivityStep[];
  /** Epoch ms when the turn started (drives the "Working" timer). */
  startedAt?: number;
  /** Epoch ms when the turn finished (drives "Worked for …"). */
  endedAt?: number;
}

/** Renders an assistant response as rich blocks. Backend directives are
 *  authoritative; the text heuristic is only a fallback when none are present. */
export function RichMessage({ text, stages, citations = [], directives, streaming = false, activity = [], startedAt, endedAt }: RichMessageProps) {
  const { thinking, answer, thinkingStreaming } = splitReasoning(text);
  const safeText = sanitizeAssistantText(answer);
  const blocks = useMemo(() => {
    if (directives && directives.length > 0) {
      const fromDirectives = directivesToBlocks(directives as Array<Record<string, unknown>>);
      // Keep any user-visible prose alongside the model's cards.
      return safeText.trim() ? [{ type: "text", text: safeText.trim() } as RichBlock, ...fromDirectives] : fromDirectives;
    }
    return parseRichResponse(safeText);
  }, [safeText, directives]);

  // Unified work trace: the collapsible "Working…/Worked for …" container holds
  // the live reasoning ("Thinking…"/"Thought Ns") and every tool step
  // ("Reading …", "Searching the web", "Editing …") in ONE place.
  const hasChain = Boolean(thinking) || activity.length > 0;

  return (
    <div className="flex flex-col gap-3">
      {streaming || hasChain ? (
        <WorkTrace
          thinking={thinking}
          thinkingStreaming={thinkingStreaming}
          activity={activity}
          streaming={streaming}
          startedAt={startedAt}
          endedAt={endedAt}
        />
      ) : stages && stages.length > 0 ? (
        <ChainOfThought className="max-w-[min(100%,72ch)] space-y-2">
          <ChainOfThoughtHeader className="px-0 py-1">Activity</ChainOfThoughtHeader>
          <ChainOfThoughtContent className="rounded-lg border border-border/45 bg-card/35 p-3 shadow-[var(--shadow-card)]">
            {stages.map((stage, i) => {
              const status = stageStatus(stage.status);
              return (
                <ChainOfThoughtStep
                  key={`${stage.stage_name}-${i}`}
                  label={status === "active" ? <ShimmerText>{prettyStage(stage.stage_name)}</ShimmerText> : prettyStage(stage.stage_name)}
                  description={status === "active" ? "Working on this step now." : status === "complete" ? "Step completed." : "Queued."}
                  status={status}
                />
              );
            })}
          </ChainOfThoughtContent>
        </ChainOfThought>
      ) : null}

      {blocks.map((block, i) => (
        <BlockView key={i} block={block} citations={citations} />
      ))}

    </div>
  );
}
