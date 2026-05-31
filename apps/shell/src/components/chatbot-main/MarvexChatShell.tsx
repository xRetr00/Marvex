import { useEffect, useRef, type ReactNode } from "react";
import type { TurnStage, UiDirective } from "@/lib/localTurn";
import { RichMessage } from "@/components/marvex/RichMessage";
import { Confirmation, ConfirmationAction, ConfirmationActions, ConfirmationRequest, ConfirmationTitle } from "@/components/confirmation";
import { QuestionTool } from "@/components/question-tool";
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

export type MarvexChatClarificationOption = { id: string; label: string; description?: string };
export type MarvexChatClarification = {
  kind: "single" | "multi" | "text";
  title: string;
  allowCustom: boolean;
  options: MarvexChatClarificationOption[];
  originalText: string;
};

export type MarvexChatMessage = {
  role: "user" | "assistant" | "system";
  text: string;
  stages?: TurnStage[];
  directives?: UiDirective[];
  approval?: { approvalId: string; traceId: string; turnId: string; text: string; status: "pending" | "approved" | "denied" | "cancelled" };
  clarification?: MarvexChatClarification;
};

export type MarvexChatShellProps = {
  messages: MarvexChatMessage[];
  micActive?: boolean;
  pending: boolean;
  onSubmit: (text: string) => void | Promise<void>;
  onApprovalDecision?: (approval: NonNullable<MarvexChatMessage["approval"]>, decision: "approve" | "deny" | "cancel") => void | Promise<void>;
  onClarificationAnswer?: (clarification: MarvexChatClarification, answerText: string) => void | Promise<void>;
  onToggleVoice?: () => void;
  renderAssistantOrb: (state?: "thinking" | "listening" | "talking" | null) => ReactNode;
  assistantOrbState?: "thinking" | "listening" | "talking" | null;
  activityLabel?: string;
};

export function MarvexChatShell({
  messages,
  micActive = false,
  pending,
  onSubmit,
  onApprovalDecision,
  onClarificationAnswer,
  onToggleVoice,
  renderAssistantOrb,
  assistantOrbState = null,
  activityLabel = "Marvex is thinking",
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
                    {message.clarification ? (
                      <QuestionTool
                        className="mt-3"
                        toolCallId={`clarify-${index}`}
                        questions={[
                          {
                            kind: message.clarification.kind,
                            title: message.clarification.title,
                            options: message.clarification.options,
                            // Always offer a free-text option so the user can
                            // answer with something not in the list.
                            allowCustom: true,
                            customLabel: "Other",
                            customPlaceholder: "Type what you mean…",
                          },
                        ]}
                        allowSkip={false}
                        onSubmitAnswer={(answer) => {
                          const clarification = message.clarification!;
                          const fromCustom = answer.text?.trim();
                          const fromOption = answer.selectedIds?.length
                            ? clarification.options.find((option) => option.id === answer.selectedIds![0])?.label
                            : undefined;
                          const answerText = fromCustom || fromOption;
                          if (answerText && !pending) {
                            void onClarificationAnswer?.(clarification, answerText);
                          }
                        }}
                      />
                    ) : null}
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
                  {activityLabel}
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
