import React, { createContext, useContext, useEffect, useState, useRef, useCallback, memo, useMemo } from "react";
import { Plus } from "lucide-react";

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
    className={`ml-auto self-center h-8 w-8 flex items-center justify-center rounded-full border-0 p-0 transition-all z-20 ${isDisabled ? "opacity-40 cursor-not-allowed bg-gray-400 text-white/60" : "opacity-90 bg-[#0A1217] text-white hover:opacity-100 cursor-pointer hover:shadow-lg"}`}
  >
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className={`block ${isDisabled ? "opacity-50" : "opacity-100"}`}>
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
        className={`w-full min-h-8 max-h-24 bg-transparent text-sm font-normal text-left self-center border-0 outline-none px-3 pr-10 py-1 z-20 relative resize-none overflow-y-auto placeholder-gray-400`}
        style={{ color: textColor, fontFamily: '"Inter", sans-serif', letterSpacing: "-0.14px", lineHeight: "22px" }}
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
        <div className="relative flex flex-col w-full bg-white/15 backdrop-blur-xl shadow-lg rounded-3xl p-2 overflow-visible group">
          <div className="flex items-center relative z-20">
            <InputArea value={value} setValue={setValue} placeholder={placeholder}
              handleKeyDown={handleKeyDown} disabled={disabled} isSubmitDisabled={isSubmitDisabled} textColor={textColor} />
          </div>
        </div>
      </form>
    </ChatInputContext.Provider>
  );
}
