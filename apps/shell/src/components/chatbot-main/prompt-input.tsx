import { Mic, MicOff, SendHorizontal } from "lucide-react";
import type { FormEvent, KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ChatbotPromptInputProps = {
  disabled?: boolean;
  micActive?: boolean;
  onSubmit: (text: string) => void | Promise<void>;
  onToggleVoice?: () => void;
  placeholder?: string;
};

export function ChatbotPromptInput({
  disabled = false,
  micActive = false,
  onSubmit,
  onToggleVoice,
  placeholder = "Ask anything...",
}: ChatbotPromptInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(180, Math.max(44, textarea.scrollHeight))}px`;
  }, [value]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const text = value.trim();
    if (!text || disabled) return;
    void onSubmit(text);
    setValue("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form className="mx-auto w-full max-w-4xl px-2 pb-3 md:px-4 md:pb-4" onSubmit={submit}>
      <div className="rounded-2xl border border-border/60 bg-card/88 p-2 shadow-[var(--shadow-composer)] backdrop-blur-xl transition-shadow focus-within:shadow-[var(--shadow-composer-focus)]">
        <textarea
          ref={textareaRef}
          className="block max-h-[180px] min-h-11 w-full resize-none border-0 bg-transparent px-2 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          value={value}
        />
        <div className="flex items-center justify-between gap-2 pt-1">
          <div className="flex items-center gap-1">
            <Button
              aria-label={micActive ? "Stop voice capture" : "Start voice capture"}
              className={cn("h-8 w-8 rounded-lg text-muted-foreground", micActive && "bg-primary text-primary-foreground hover:bg-primary/90")}
              onClick={onToggleVoice}
              size="icon"
              type="button"
              variant={micActive ? "default" : "ghost"}
            >
              {micActive ? <MicOff size={16} /> : <Mic size={16} />}
            </Button>
          </div>
          <Button aria-label="Send message" className="h-8 w-8 rounded-lg" disabled={disabled || !value.trim()} size="icon" type="submit">
            <SendHorizontal size={16} />
          </Button>
        </div>
      </div>
    </form>
  );
}
