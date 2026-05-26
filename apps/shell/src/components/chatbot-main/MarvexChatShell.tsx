import { useEffect, useRef, type ReactNode } from "react";
import type { TurnStage, UiDirective } from "@/lib/localTurn";
import { RichMessage } from "@/components/marvex/RichMessage";
import {
  ChatbotAssistantFrame,
  ChatbotCopyAction,
  ChatbotMessage,
  ChatbotMessageActions,
  ChatbotMessageContent,
} from "./message";
import {
  ChatbotConversation,
  ChatbotConversationContent,
  ChatbotConversationEmpty,
  ChatbotScrollButton,
} from "./conversation";
import { ChatbotPromptInput } from "./prompt-input";

export type MarvexChatMessage = {
  role: "user" | "assistant" | "system";
  text: string;
  stages?: TurnStage[];
  directives?: UiDirective[];
};

export type MarvexChatShellProps = {
  messages: MarvexChatMessage[];
  micActive?: boolean;
  pending: boolean;
  onSubmit: (text: string) => void | Promise<void>;
  onToggleVoice?: () => void;
  renderAssistantOrb: (state?: "thinking" | "listening" | "talking" | null) => ReactNode;
  assistantOrbState?: "thinking" | "listening" | "talking" | null;
};

export function MarvexChatShell({
  messages,
  micActive = false,
  pending,
  onSubmit,
  onToggleVoice,
  renderAssistantOrb,
  assistantOrbState = null,
}: MarvexChatShellProps) {
  const conversationRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const node = conversationRef.current;
    if (!node) return;
    if (typeof node.scrollTo === "function") {
      node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
    } else {
      node.scrollTop = node.scrollHeight;
    }
  }, [messages, pending]);

  return (
    <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
      <ChatbotConversation ref={conversationRef} className={messages.length > 0 ? "bg-background/80" : "bg-transparent"}>
        {messages.length === 0 && !pending ? <ChatbotConversationEmpty /> : null}
        <ChatbotConversationContent>
          {messages.map((message, index) => (
            <ChatbotMessage key={`${message.role}-${index}`} from={message.role}>
              {message.role === "assistant" ? (
                <ChatbotAssistantFrame orb={renderAssistantOrb(assistantOrbState)}>
                  <ChatbotMessageContent from="assistant">
                    <RichMessage text={message.text} stages={message.stages} directives={message.directives} />
                  </ChatbotMessageContent>
                  <ChatbotMessageActions className="mt-2">
                    <ChatbotCopyAction text={message.text} />
                  </ChatbotMessageActions>
                </ChatbotAssistantFrame>
              ) : (
                <ChatbotMessageContent from={message.role}>{message.text}</ChatbotMessageContent>
              )}
            </ChatbotMessage>
          ))}
          {pending ? (
            <ChatbotMessage from="assistant">
              <ChatbotAssistantFrame orb={renderAssistantOrb("thinking")}>
                <ChatbotMessageContent from="assistant" className="text-muted-foreground">
                  Marvex is thinking
                </ChatbotMessageContent>
              </ChatbotAssistantFrame>
            </ChatbotMessage>
          ) : null}
        </ChatbotConversationContent>
      </ChatbotConversation>
      <ChatbotScrollButton targetRef={conversationRef} />
      <div className="border-t border-border/30 bg-background/86 pt-3 backdrop-blur-xl">
        <ChatbotPromptInput disabled={pending} micActive={micActive} onSubmit={onSubmit} onToggleVoice={onToggleVoice} />
      </div>
    </section>
  );
}
