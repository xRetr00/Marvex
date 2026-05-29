import { Mic, MicOff, SendHorizontal, Square } from "lucide-react";
import type { FormEvent, KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AssistantStatusKind } from "@/lib/assistantState";

export type ChatbotPromptInputProps = {
  disabled?: boolean;
  micActive?: boolean;
  agentStatus?: AssistantStatusKind;
  onSubmit: (text: string) => void | Promise<void>;
  onToggleVoice?: () => void;
  placeholder?: string;
};

const ACTIVE_STATUSES: AssistantStatusKind[] = [
  "thinking", "working", "using_tools", "mcp", "skills", "searching_web", "talking",
];

const STATUS_HINT: Partial<Record<AssistantStatusKind, string>> = {
  thinking: "Thinking...",
  working: "Working...",
  using_tools: "Using tools...",
  mcp: "Running MCP...",
  skills: "Running skill...",
  searching_web: "Searching the web...",
  listening: "Listening...",
  talking: "Speaking...",
  needs_approval: "Waiting for approval",
  asking: "Waiting for your response",
};

export function ChatbotPromptInput({
  disabled = false,
  micActive = false,
  agentStatus = "idle",
  onSubmit,
  onToggleVoice,
  placeholder = "Ask anything...",
}: ChatbotPromptInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const isAgentActive = ACTIVE_STATUSES.includes(agentStatus);
  const hint = STATUS_HINT[agentStatus];

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(200, Math.max(44, textarea.scrollHeight))}px`;
  }, [value]);

  // Re-focus after agent finishes
  useEffect(() => {
    if (!disabled && !isAgentActive) {
      textareaRef.current?.focus();
    }
  }, [disabled, isAgentActive]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const text = value.trim();
    if (!text || disabled) return;
    void onSubmit(text);
    setValue("");
    // Reset height after clearing
    if (textareaRef.current) {
      textareaRef.current.style.height = "44px";
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      className="marvex-composer mx-auto w-full max-w-3xl px-3 pb-3 md:px-5 md:pb-4"
      onSubmit={submit}
      aria-label="Message composer"
    >
      <div
        className={cn(
          "marvex-composer-box",
          "rounded-2xl border bg-card/90 shadow-[var(--shadow-composer)] backdrop-blur-xl",
          "transition-all duration-200",
          "focus-within:shadow-[var(--shadow-composer-focus)] focus-within:border-border/70",
          isAgentActive && "border-border/60 opacity-80",
          !isAgentActive && "border-border/40",
        )}
      >
        {/* Agent activity hint strip */}
        {hint && (
          <div className="marvex-composer-hint flex items-center gap-2 px-4 pt-2.5 pb-0">
            <span className="marvex-hint-dot" />
            <span className="text-xs text-muted-foreground">{hint}</span>
          </div>
        )}

        <textarea
          ref={textareaRef}
          className="marvex-composer-textarea block max-h-[200px] min-h-[44px] w-full resize-none border-0 bg-transparent px-4 py-3 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground/60 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={isAgentActive ? "" : placeholder}
          value={value}
          aria-label="Message input"
          aria-multiline="true"
          rows={1}
        />

        <div className="marvex-composer-actions flex items-center justify-between gap-2 px-2.5 pb-2">
          {/* Left — voice toggle */}
          <div className="flex items-center gap-1">
            <Button
              aria-label={micActive ? "Stop voice capture" : "Start voice capture"}
              className={cn(
                "h-8 w-8 rounded-xl text-muted-foreground",
                micActive && "bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20",
              )}
              onClick={onToggleVoice}
              size="icon"
              type="button"
              variant={micActive ? "ghost" : "ghost"}
              title={micActive ? "Stop listening" : "Start voice input"}
            >
              {micActive ? <MicOff size={15} /> : <Mic size={15} />}
            </Button>

            {/* Char count hint for long messages */}
            {value.length > 200 && (
              <span className="ml-1 text-[11px] tabular-nums text-muted-foreground/60">
                {value.length}
              </span>
            )}
          </div>

          {/* Right — send / stop */}
          <Button
            aria-label={disabled ? "Stop generation" : "Send message"}
            className={cn(
              "h-8 w-8 rounded-xl transition-all",
              !disabled && value.trim() && "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm",
              disabled && "bg-muted/60 text-muted-foreground border-border/40",
            )}
            disabled={!disabled && !value.trim()}
            size="icon"
            type={disabled ? "button" : "submit"}
            onClick={disabled ? () => undefined : undefined}
          >
            {disabled ? <Square size={13} className="fill-current" /> : <SendHorizontal size={15} />}
          </Button>
        </div>
      </div>

      <p className="mt-1.5 px-1 text-center text-[10px] text-muted-foreground/40">
        Enter to send &middot; Shift+Enter for new line
      </p>
    </form>
  );
}
