import React, { createContext, useContext, useEffect, useState, useRef, useCallback, memo, useMemo } from "react";

type MenuOption = "Auto" | "Max" | "Search" | "Plan";

interface ChatInputProps {
  placeholder?: string;
  onSubmit?: (value: string) => void;
  disabled?: boolean;
  glowIntensity?: number;
  expandOnFocus?: boolean;
  animationDuration?: number;
  textColor?: string;
  backgroundOpacity?: number;
  showEffects?: boolean;
  menuOptions?: MenuOption[];
}

interface ChatInputContextProps {
  textColor: string;
  showEffects: boolean;
}

const ChatInputContext = createContext<ChatInputContextProps | undefined>(undefined);

function useChatInputContext() {
  const ctx = useContext(ChatInputContext);
  if (!ctx) throw new Error("useChatInputContext must be used within a ChatInputProvider");
  return ctx;
}

const SendButton = memo(({ isDisabled, textColor }: { isDisabled: boolean; textColor: string }) => (
  <button
    type="submit"
    aria-label="Send message"
    disabled={isDisabled}
    className={`ml-auto self-center h-7 w-7 flex items-center justify-center rounded-xl border-0 p-0 transition-all z-20 ${isDisabled ? "cursor-not-allowed bg-muted text-muted-foreground/25" : "bg-foreground text-background hover:opacity-85 active:scale-95 cursor-pointer"}`}
  >
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className={`block ${isDisabled ? "opacity-50" : "opacity-100"}`}>
      <path d="M16 22L16 10M16 10L11 15M16 10L21 15" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  </button>
));

const InputArea = memo(({ value, setValue, placeholder, handleKeyDown, disabled, isSubmitDisabled, textColor }: {
  value: string; setValue: React.Dispatch<React.SetStateAction<string>>;
  placeholder: string; handleKeyDown: (e: React.KeyboardEvent) => void;
  disabled: boolean; isSubmitDisabled: boolean; textColor: string;
}) => {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = Math.min(scrollHeight, 22 * 4 + 16) + "px";
    }
  }, [value]);
  return (
    <div className="flex-1 relative h-full flex items-center">
      <textarea
        ref={textareaRef} value={value} onChange={(e) => setValue(e.target.value)} onKeyDown={handleKeyDown}
        placeholder={placeholder} aria-label="Message Input" rows={1}
        className="w-full min-h-24 max-h-36 bg-transparent text-[13px] font-normal text-left self-center border-0 outline-none px-4 pr-10 pt-3.5 pb-1.5 z-20 relative resize-none overflow-y-auto placeholder:text-muted-foreground/35"
        style={{ color: textColor, fontFamily: '"Inter", sans-serif', letterSpacing: 0, lineHeight: "1.65" }}
        disabled={disabled}
      />
      <SendButton isDisabled={isSubmitDisabled} textColor={textColor} />
    </div>
  );
});

export default function ChatInput({
  placeholder = "Ask Marvex...",
  onSubmit,
  disabled = false,
  glowIntensity = 0.4,
  expandOnFocus = true,
  animationDuration = 500,
  textColor = "#0A1217",
  backgroundOpacity = 0.15,
  showEffects = true,
  menuOptions = ["Auto", "Max", "Search", "Plan"] as MenuOption[],
}: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && onSubmit && !disabled) { onSubmit(value.trim()); setValue(""); }
  }, [value, onSubmit, disabled]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(e as unknown as React.FormEvent); }
  }, [handleSubmit]);

  const isSubmitDisabled = disabled || !value.trim();

  const ctx = useMemo(() => ({ textColor, showEffects }), [textColor, showEffects]);

  return (
    <ChatInputContext.Provider value={ctx}>
      <form onSubmit={handleSubmit} className="w-full">
        <div className="relative flex flex-col w-full overflow-visible rounded-2xl border border-border/30 bg-card/70 p-2 shadow-[var(--shadow-composer)] transition-shadow duration-300 focus-within:shadow-[var(--shadow-composer-focus)] group">
          <div className="flex items-center relative z-20">
            <InputArea value={value} setValue={setValue} placeholder={placeholder}
              handleKeyDown={handleKeyDown} disabled={disabled} isSubmitDisabled={isSubmitDisabled} textColor={textColor} />
          </div>
        </div>
      </form>
    </ChatInputContext.Provider>
  );
}
