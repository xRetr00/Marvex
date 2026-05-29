import { useEffect, useRef, useState, useCallback, type ReactNode } from "react";
import type { TurnStage, UiDirective } from "@/lib/localTurn";
import type { AssistantStatusKind } from "@/lib/assistantState";
import { RichMessage } from "@/components/marvex/RichMessage";
import { Confirmation, ConfirmationAction, ConfirmationActions, ConfirmationRequest, ConfirmationTitle } from "@/components/confirmation";
import {
  ChatbotAssistantFrame,
  ChatbotCopyAction,
  ChatbotMessage,
  ChatbotMessageActions,
  ChatbotMessageContent,
  ChatbotRetryAction,
} from "./message";
import {
  ChatbotConversation,
  ChatbotConversationContent,
  ChatbotConversationEmpty,
  ChatbotScrollButton,
} from "./conversation";
import { ChatbotPromptInput } from "./prompt-input";
import { AgentStatusBar } from "./agent-status-bar";

export type MarvexChatMessage = {
  role: "user" | "assistant" | "system";
  text: string;
  stages?: TurnStage[];
  directives?: UiDirective[];
  approval?: { approvalId: string; traceId: string; turnId: string; text: string; status: "pending" | "approved" | "denied" | "cancelled" };
};

export type MarvexChatShellProps = {
  messages: MarvexChatMessage[];
  micActive?: boolean;
  pending: boolean;
  agentStatus?: AssistantStatusKind;
  onSubmit: (text: string) => void | Promise<void>;
  onApprovalDecision?: (approval: NonNullable<MarvexChatMessage["approval"]>, decision: "approve" | "deny" | "cancel") => void | Promise<void>;
  onToggleVoice?: () => void;
  renderAssistantOrb: (state?: "thinking" | "listening" | "talking" | null) => ReactNode;
  assistantOrbState?: "thinking" | "listening" | "talking" | null;
};

export function MarvexChatShell({
  messages,
  micActive = false,
  pending,
  agentStatus = "idle",
  onSubmit,
  onApprovalDecision,
  onToggleVoice,
  renderAssistantOrb,
  assistantOrbState = null,
}: MarvexChatShellProps) {
  const conversationRef = useRef<HTMLDivElement | null>(null);
  // Fix #1 + #2: track whether user is near bottom to gate auto-scroll and scroll button
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const isNearBottomRef = useRef(true);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const node = conversationRef.current;
    if (!node) return;
    if (typeof node.scrollTo === "function") node.scrollTo({ top: node.scrollHeight, behavior });
    else node.scrollTop = node.scrollHeight;
  }, []);

  // Track scroll position to know if user has scrolled up
  useEffect(() => {
    const node = conversationRef.current;
    if (!node) return;
    const onScroll = () => {
      const distFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
      isNearBottomRef.current = distFromBottom < 80;
      setShowScrollBtn(distFromBottom > 120);
    };
    node.addEventListener("scroll", onScroll, { passive: true });
    return () => node.removeEventListener("scroll", onScroll);
  }, []);

  // Fix #2: only auto-scroll when the user hasn't scrolled up to read history
  useEffect(() => {
    if (isNearBottomRef.current) {
      scrollToBottom("smooth");
    }
  }, [messages, pending, scrollToBottom]);

  // Fix #7: retry handler re-submits the last user message
  const retryLastMessage = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) void onSubmit(lastUser.text);
  }, [messages, onSubmit]);

  return (
    <section className="marvex-shell-section relative flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Agent status bar — shows live detail while working */}
      <AgentStatusBar status={agentStatus} pending={pending} />

      <ChatbotConversation ref={conversationRef} className="marvex-conversation">
        {messages.length === 0 && !pending ? <ChatbotConversationEmpty /> : null}
        <ChatbotConversationContent>
          {messages.map((message, index) => {
            const isLastAssistant = message.role === "assistant" && index === messages.length - 1 && !pending;
            return (
              <ChatbotMessage key={`${message.role}-${index}`} from={message.role}>
                {message.role === "assistant" ? (
                  <ChatbotAssistantFrame orb={renderAssistantOrb(assistantOrbState)}>
                    <ChatbotMessageContent from="assistant">
                      <RichMessage text={message.text} stages={message.stages} directives={message.directives} />
                      {message.approval ? (
                        <Confirmation
                          approval={message.approval.status === "pending" ? { id: message.approval.approvalId } : { id: message.approval.approvalId, approved: message.approval.status === "approved" }}
                          state={message.approval.status === "pending" ? "approval-requested" : "approval-responded"}
                          className="mt-3"
                        >
                          <ConfirmationTitle>Approval required for this action.</ConfirmationTitle>
                          <ConfirmationRequest>
                            <ConfirmationActions>
                              <ConfirmationAction disabled={!onApprovalDecision || pending} onClick={() => void onApprovalDecision?.(message.approval!, "approve")}>Approve</ConfirmationAction>
                              <ConfirmationAction disabled={!onApprovalDecision || pending} variant="outline" onClick={() => void onApprovalDecision?.(message.approval!, "deny")}>Deny</ConfirmationAction>
                              <ConfirmationAction disabled={!onApprovalDecision || pending} variant="ghost" onClick={() => void onApprovalDecision?.(message.approval!, "cancel")}>Cancel</ConfirmationAction>
                            </ConfirmationActions>
                          </ConfirmationRequest>
                        </Confirmation>
                      ) : null}
                    </ChatbotMessageContent>
                    <ChatbotMessageActions className="mt-2">
                      <ChatbotCopyAction text={message.text} />
                      {/* Fix #7: wire retry on the last assistant turn */}
                      {isLastAssistant && <ChatbotRetryAction onRetry={retryLastMessage} />}
                    </ChatbotMessageActions>
                  </ChatbotAssistantFrame>
                ) : (
                  <ChatbotMessageContent from={message.role}>{message.text}</ChatbotMessageContent>
                )}
              </ChatbotMessage>
            );
          })}
          {pending ? (
            <ChatbotMessage from="assistant">
              <ChatbotAssistantFrame orb={renderAssistantOrb("thinking")}>
                <ThinkingBubble />
              </ChatbotAssistantFrame>
            </ChatbotMessage>
          ) : null}
        </ChatbotConversationContent>
      </ChatbotConversation>

      {/* Fix #1: only show scroll button when user is actually scrolled up */}
      {showScrollBtn && <ChatbotScrollButton targetRef={conversationRef} onScrolled={() => setShowScrollBtn(false)} />}

      <div className="marvex-prompt-dock">
        <ChatbotPromptInput disabled={pending} micActive={micActive} onSubmit={onSubmit} onToggleVoice={onToggleVoice} agentStatus={agentStatus} />
      </div>
    </section>
  );
}

// Animated thinking indicator — three pulsing dots with staggered delay
function ThinkingBubble() {
  return (
    <ChatbotMessageContent from="assistant" className="marvex-thinking-bubble">
      <span className="marvex-thinking-dots" aria-label="Marvex is thinking">
        <span className="marvex-dot" style={{ animationDelay: "0ms" }} />
        <span className="marvex-dot" style={{ animationDelay: "160ms" }} />
        <span className="marvex-dot" style={{ animationDelay: "320ms" }} />
      </span>
    </ChatbotMessageContent>
  );
}
