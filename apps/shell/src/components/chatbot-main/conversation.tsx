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
      className={cn("relative flex-1 overflow-y-auto overscroll-contain", className)}
      {...props}
    />
  ),
);
ChatbotConversation.displayName = "ChatbotConversation";

export function ChatbotConversationContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mx-auto flex min-h-full min-w-0 max-w-4xl flex-col gap-5 px-2 py-6 md:gap-7 md:px-4", className)} {...props} />;
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
        <div className="grid max-w-md gap-2">
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
          <p className="text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
      )}
    </div>
  );
}

export function ChatbotScrollButton({ targetRef }: { targetRef: RefObject<HTMLDivElement | null> }) {
  return (
    <Button
      aria-label="Scroll to bottom"
      className="absolute bottom-28 left-1/2 z-10 h-8 -translate-x-1/2 rounded-full border-border/50 bg-card/90 px-3 shadow-[var(--shadow-float)] backdrop-blur-lg md:bottom-32"
      onClick={() => {
        const node = targetRef.current;
        if (!node) return;
        if (typeof node.scrollTo === "function") node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
        else node.scrollTop = node.scrollHeight;
      }}
      size="sm"
      type="button"
      variant="outline"
    >
      <ArrowDown size={14} />
    </Button>
  );
}
