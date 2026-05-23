import { useMemo } from "react";
import { parseRichResponse, directivesToBlocks, type RichBlock } from "@/lib/richContent";
import type { TurnStage, UiDirective } from "@/lib/localTurn";
import {
  ChainOfThought,
  ChainOfThoughtHeader,
  ChainOfThoughtContent,
  ChainOfThoughtStep,
} from "@/components/chain-of-thought";
import ProductCard from "@/components/product-card";
import { ExpandableCard } from "@/components/expandable-card";
import AgentPlan from "@/components/agent-plan";
import { AlertBadge } from "@/components/alert-badge";
import ButtonCopy from "@/components/button-copy";

function stageStatus(status: string): "complete" | "active" | "pending" {
  if (["completed", "succeeded", "ok", "done"].includes(status)) return "complete";
  if (["in_progress", "running", "active", "started"].includes(status)) return "active";
  return "pending";
}

function prettyStage(name: string): string {
  return name.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function BlockView({ block }: { block: RichBlock }) {
  switch (block.type) {
    case "text":
      return <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{block.text}</p>;
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

export interface RichMessageProps {
  text: string;
  stages?: TurnStage[];
  /** Backend model-driven directives; when present they drive rendering (not keyword heuristics). */
  directives?: UiDirective[];
}

/** Renders an assistant response as rich blocks. Backend directives are
 *  authoritative; the text heuristic is only a fallback when none are present. */
export function RichMessage({ text, stages, directives }: RichMessageProps) {
  const blocks = useMemo(() => {
    if (directives && directives.length > 0) {
      const fromDirectives = directivesToBlocks(directives as Array<Record<string, unknown>>);
      // Keep any user-visible prose alongside the model's cards.
      return text.trim() ? [{ type: "text", text: text.trim() } as RichBlock, ...fromDirectives] : fromDirectives;
    }
    return parseRichResponse(text);
  }, [text, directives]);

  return (
    <div className="flex flex-col gap-3">
      {stages && stages.length > 0 && (
        <ChainOfThought defaultOpen={false}>
          <ChainOfThoughtHeader>Reasoning</ChainOfThoughtHeader>
          <ChainOfThoughtContent>
            {stages.map((stage, i) => (
              <ChainOfThoughtStep key={`${stage.stage_name}-${i}`} label={prettyStage(stage.stage_name)} status={stageStatus(stage.status)} />
            ))}
          </ChainOfThoughtContent>
        </ChainOfThought>
      )}

      {blocks.map((block, i) => (
        <BlockView key={i} block={block} />
      ))}

      <div className="flex justify-end">
        <ButtonCopy onCopy={() => void navigator.clipboard?.writeText(text)} />
      </div>
    </div>
  );
}
