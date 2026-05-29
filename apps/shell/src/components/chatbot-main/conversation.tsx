import { ArrowDown } from "lucide-react";
import type { HTMLAttributes, ReactNode, RefObject } from "react";
import { forwardRef } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ChatbotConversationProps = HTMLAttributes<HTMLDivElement>;

export const ChatbotConversation = forwardRef<HTMLDivElement, ChatbotConversationProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="log"
      aria-label="Conversation"
      className={cn("relative flex-1 overflow-y-auto overscroll-contain", className)}
      {...props}
    />
  ),
);
ChatbotConversation.displayName = "ChatbotConversation";

export function ChatbotConversationContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mx-auto flex min-h-full min-w-0 max-w-3xl flex-col gap-6 px-3 py-8 md:gap-8 md:px-5", className)} {...props} />;
}

export function ChatbotConversationEmpty({
  title = "How can I help you today?",
  description = "Ask Marvex to search, plan, inspect runtime state, or work in this workspace.",
  children,
  className,
}: {
  title?: string;
  description?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("pointer-events-none absolute inset-0 z-10 flex items-center justify-center p-8 text-center", className)}>
      {children ?? (
        <div className="grid max-w-sm gap-3">
          <div className="marvex-empty-icon mx-auto" aria-hidden="true" />
          <h2 className="text-balance text-[15px] font-semibold text-foreground">{title}</h2>
          <p className="text-pretty text-sm leading-relaxed text-muted-foreground">{description}</p>
        </div>
      )}
    </div>
  );
}

// Fix #1: accepts onScrolled callback so parent can hide button after click
export function ChatbotScrollButton({
  targetRef,
  onScrolled,
}: {
  targetRef: RefObject<HTMLDivElement | null>;
  onScrolled?: () => void;
}) {
  return (
    <Button
      aria-label="Scroll to bottom"
      className="marvex-scroll-btn absolute bottom-[72px] left-1/2 z-20 h-8 -translate-x-1/2 rounded-full border-border/50 bg-card/90 px-3 shadow-[var(--shadow-float)] backdrop-blur-lg"
      onClick={() => {
        const node = targetRef.current;
        if (!node) return;
        if (typeof node.scrollTo === "function") node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
        else node.scrollTop = node.scrollHeight;
        onScrolled?.();
      }}
      size="sm"
      type="button"
      variant="outline"
    >
      <ArrowDown size={13} />
      <span className="ml-1 text-xs text-muted-foreground">Jump to bottom</span>
    </Button>
  );
}
