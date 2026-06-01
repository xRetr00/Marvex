import { ChevronDown, Mic, MicOff, Plus, SendHorizontal, Square } from "lucide-react";
import type { FormEvent, KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ChatbotPromptInputProps = {
  disabled?: boolean;
  generating?: boolean;
  micActive?: boolean;
  onSubmit: (text: string) => void | Promise<void>;
  onStop?: () => void;
  onToggleVoice?: () => void;
  placeholder?: string;
  modelLabel?: string;
  models?: Array<{ id: string; name: string; provider?: string; active?: boolean }>;
  onSelectModel?: (modelId: string) => void | Promise<void>;
};

export function ChatbotPromptInput({
  disabled = false,
  generating = false,
  micActive = false,
  onSubmit,
  onStop,
  onToggleVoice,
  placeholder = "Ask anything...",
  modelLabel = "Assistant runtime",
  models = [],
  onSelectModel,
}: ChatbotPromptInputProps) {
  const [value, setValue] = useState("");
  const [modelOpen, setModelOpen] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [hints, setHints] = useState<string[]>([]);
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
    if (!text || disabled || generating) return;
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
      <div className="group relative overflow-visible rounded-3xl border border-border/60 bg-card/78 p-2 shadow-[var(--shadow-composer)] backdrop-blur-2xl transition-shadow focus-within:shadow-[var(--shadow-composer-focus)]">
        <div className="pointer-events-none absolute inset-0 rounded-3xl opacity-0 transition-opacity duration-300 group-hover:opacity-100 group-focus-within:opacity-100" style={{ boxShadow: "0 0 0 1px color-mix(in srgb, var(--primary) 18%, transparent), 0 0 30px color-mix(in srgb, var(--primary) 14%, transparent)" }} />
        <textarea
          ref={textareaRef}
          className="relative z-10 block max-h-[180px] min-h-11 w-full resize-none border-0 bg-transparent px-3 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          value={value}
        />
        {hints.length > 0 ? (
          <div className="relative z-10 flex flex-wrap gap-1.5 px-2 pb-1">
            {hints.map((hint) => (
              <button key={hint} type="button" onClick={() => setHints((items) => items.filter((item) => item !== hint))} className="rounded-full border border-border/60 bg-secondary/70 px-2 py-0.5 text-[11px] text-muted-foreground">
                {hint}
              </button>
            ))}
          </div>
        ) : null}
        <div className="relative z-10 flex items-center justify-between gap-2 pt-1">
          <div className="flex min-w-0 items-center gap-2">
            <div className="relative">
              <Button aria-label="Composer tools" className="h-8 w-8 rounded-full text-muted-foreground" onClick={() => setToolsOpen((open) => !open)} size="icon" type="button" variant="ghost">
                <Plus size={16} />
              </Button>
              {toolsOpen ? (
                <div className="absolute bottom-10 left-0 z-30 grid min-w-32 gap-1 rounded-lg border border-border bg-popover p-1 text-xs text-popover-foreground shadow-[var(--shadow-float)]">
                  {["Auto", "Search", "Plan"].map((hint) => (
                    <button key={hint} type="button" className="rounded-md px-3 py-2 text-left hover:bg-accent" onClick={() => { setHints((items) => items.includes(hint) ? items : [...items, hint]); setToolsOpen(false); }}>
                      {hint}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
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
            <div className="relative">
              <Button aria-label="Select model" className="h-8 max-w-[220px] rounded-full px-2 text-xs text-muted-foreground" onClick={() => setModelOpen((open) => !open)} type="button" variant="ghost">
                <ModelLogo provider={models.find((model) => model.active)?.provider} />
                <span className="truncate">{modelLabel}</span>
                <ChevronDown size={13} />
              </Button>
              {modelOpen ? (
                <div className="absolute bottom-10 left-0 z-30 w-72 rounded-xl border border-border bg-popover p-1 text-popover-foreground shadow-[var(--shadow-float)]">
                  <div className="px-2 py-1.5 text-[11px] font-semibold text-muted-foreground">Model selector</div>
                  <div className="max-h-72 overflow-auto">
                    {(models.length ? models : [{ id: modelLabel, name: modelLabel, provider: "synthetic", active: true }]).map((model) => (
                      <button
                        key={model.id}
                        type="button"
                        className={cn("flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs hover:bg-accent", model.active && "bg-accent/70 text-accent-foreground")}
                        onClick={() => { setModelOpen(false); void onSelectModel?.(model.id); }}
                      >
                        <ModelLogo provider={model.provider} />
                        <span className="min-w-0 flex-1 truncate">{model.name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
            <span className="hidden text-[11px] tabular-nums text-muted-foreground sm:inline">{value.length} / 12000</span>
          </div>
          {generating ? (
            <Button aria-label="Stop generation" className="h-8 w-8 rounded-lg" onClick={onStop} size="icon" type="button" variant="outline">
              <Square size={14} />
            </Button>
          ) : (
            <Button aria-label="Send message" className="h-8 w-8 rounded-lg" disabled={disabled || !value.trim()} size="icon" type="submit">
              <SendHorizontal size={16} />
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}

function ModelLogo({ provider }: { provider?: string }) {
  if (!provider) return <span className="size-4 rounded-full bg-primary/50" />;
  return <img alt="" className="size-4 rounded-full dark:invert" src={`https://models.dev/logos/${provider}.svg`} onError={(event) => { event.currentTarget.style.display = "none"; }} />;
}
