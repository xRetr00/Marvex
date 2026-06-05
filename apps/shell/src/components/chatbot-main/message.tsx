import type { ComponentProps, HTMLAttributes, ReactNode } from "react";
import { Copy, Pencil, RotateCcw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ChatbotMessageProps = HTMLAttributes<HTMLDivElement> & {
  from: "system" | "user" | "assistant";
};

export function ChatbotMessage({ className, from, ...props }: ChatbotMessageProps) {
  return (
    <article
      className={cn(
        "group flex w-full max-w-[95%] flex-col gap-2",
        from === "user" ? "is-user ml-auto items-end" : "is-assistant items-start",
        from === "system" && "is-system mx-auto max-w-[min(100%,38rem)] items-center",
        className,
      )}
      data-message-role={from}
      {...props}
    />
  );
}

export type ChatbotMessageContentProps = HTMLAttributes<HTMLDivElement> & {
  from: "system" | "user" | "assistant";
};

export function ChatbotMessageContent({ className, from, ...props }: ChatbotMessageContentProps) {
  return (
    <div
      className={cn(
        "flex min-w-0 max-w-full flex-col gap-2 overflow-hidden text-sm leading-[1.65] text-foreground",
        from === "user" && "w-fit max-w-[min(80%,56ch)] break-words rounded-2xl rounded-br-lg border border-border/30 bg-gradient-to-br from-secondary to-muted px-3.5 py-2 shadow-[var(--shadow-card)]",
        from === "assistant" && "w-full max-w-[min(100%,72ch)]",
        from === "system" && "rounded-full border border-border/40 bg-card/45 px-3 py-1 text-xs text-muted-foreground shadow-[var(--shadow-card)]",
        className,
      )}
      {...props}
    />
  );
}

export function ChatbotAssistantFrame({ children, orb }: { children: ReactNode; orb?: ReactNode }) {
  return (
    <div className="flex w-full items-start gap-3">
      {orb ? <div className="marvex-message-orb mt-0.5">{orb}</div> : null}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export type ChatbotMessageActionsProps = ComponentProps<"div">;

export function ChatbotMessageActions({ className, ...props }: ChatbotMessageActionsProps) {
  return <div className={cn("flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100", className)} {...props} />;
}

export function ChatbotCopyAction({ text }: { text: string }) {
  return (
    <Button
      aria-label="Copy message"
      size="icon"
      type="button"
      variant="ghost"
      className="h-7 w-7 text-muted-foreground"
      onClick={() => void navigator.clipboard?.writeText(text)}
    >
      <Copy size={13} />
    </Button>
  );
}

export function ChatbotRetryAction({ onRetry }: { onRetry?: () => void }) {
  if (!onRetry) return null;
  return (
    <Button aria-label="Retry response" title="Retry response" size="icon" type="button" variant="ghost" className="h-7 w-7 text-muted-foreground" onClick={onRetry}>
      <RotateCcw size={13} />
    </Button>
  );
}

export function ChatbotEditAction({ onEdit }: { onEdit?: () => void }) {
  if (!onEdit) return null;
  return (
    <Button aria-label="Edit message" title="Edit message" size="icon" type="button" variant="ghost" className="h-7 w-7 text-muted-foreground" onClick={onEdit}>
      <Pencil size={13} />
    </Button>
  );
}

export function ChatbotDeleteAction({ onDelete, label = "Delete message" }: { onDelete?: () => void; label?: string }) {
  if (!onDelete) return null;
  return (
    <Button aria-label={label} title={label} size="icon" type="button" variant="ghost" className="h-7 w-7 text-muted-foreground hover:text-destructive" onClick={onDelete}>
      <Trash2 size={13} />
    </Button>
  );
}
