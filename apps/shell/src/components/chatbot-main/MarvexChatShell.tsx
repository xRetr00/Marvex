import { useEffect, useRef, type ReactNode } from "react";
import type { CitationRef, TurnStage, UiDirective } from "@/lib/localTurn";
import { RichMessage } from "@/components/marvex/RichMessage";
import { stripReasoning } from "@/lib/reasoning";
import { type ActivityStep } from "@/lib/activityLabels";
import { Confirmation, ConfirmationAction, ConfirmationActions, ConfirmationRequest, ConfirmationTitle } from "@/components/confirmation";
import { QuestionTool } from "@/components/question-tool";
import {
  ChatbotAssistantFrame,
  ChatbotCopyAction,
  ChatbotDeleteAction,
  ChatbotEditAction,
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
import { WorkTrace } from "./work-trace";

export type MarvexChatClarificationOption = { id: string; label: string; description?: string };
export type MarvexChatClarification = {
  kind: "single" | "multi" | "text";
  title: string;
  allowCustom: boolean;
  options: MarvexChatClarificationOption[];
  originalText: string;
  answerText?: string;
};

export type MarvexChatMessage = {
  id?: string;
  role: "user" | "assistant" | "system";
  text: string;
  providerResponseId?: string;
  previousResponseId?: string;
  editedAt?: number;
  commentary?: string[];
  stages?: TurnStage[];
  citations?: CitationRef[];
  directives?: UiDirective[];
  approval?: { approvalId: string; traceId: string; turnId: string; text: string; status: "pending" | "approved" | "denied" | "cancelled" };
  clarification?: MarvexChatClarification;
  streaming?: boolean;
  activity?: ActivityStep[];
  activityStartedAt?: number;
  activityEndedAt?: number;
};

export type MarvexChatShellProps = {
  messages: MarvexChatMessage[];
  micActive?: boolean;
  pending: boolean;
  onSubmit: (text: string) => void | Promise<void>;
  onStop?: () => void;
  onDeleteMessage?: (messageId: string) => void | Promise<void>;
  onEditUserMessage?: (messageId: string, currentText: string) => void | Promise<void>;
  onRetryAssistantMessage?: (messageId: string) => void | Promise<void>;
  onApprovalDecision?: (approval: NonNullable<MarvexChatMessage["approval"]>, decision: "approve" | "deny" | "cancel") => void | Promise<void>;
  onClarificationAnswer?: (clarification: MarvexChatClarification, answerText: string) => void | Promise<void>;
  onToggleVoice?: () => void;
  voiceSessionActive?: boolean;
  voiceSessionListening?: boolean;
  voiceSessionCue?: string;
  onToggleVoiceSession?: () => void;
  composerValue?: string;
  onComposerValueChange?: (value: string) => void;
  renderAssistantOrb: (state?: "thinking" | "listening" | "talking" | null) => ReactNode;
  assistantOrbState?: "thinking" | "listening" | "talking" | null;
  modelLabel?: string;
  models?: Array<{ id: string; name: string; provider?: string; active?: boolean }>;
  onSelectModel?: (modelId: string) => void | Promise<void>;
  contextInputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  reasoningTokens?: number;
  contextWindow?: number;
  cachedInputTokens?: number;
  reasoningEffort?: string;
  reasoningEffortOptions?: string[];
  onSelectReasoningEffort?: (effort: string) => void | Promise<void>;
};

export function MarvexChatShell({
  messages,
  micActive = false,
  pending,
  onSubmit,
  onStop,
  onDeleteMessage,
  onEditUserMessage,
  onRetryAssistantMessage,
  onApprovalDecision,
  onClarificationAnswer,
  onToggleVoice,
  voiceSessionActive = false,
  voiceSessionListening = false,
  voiceSessionCue = "",
  onToggleVoiceSession,
  composerValue,
  onComposerValueChange,
  renderAssistantOrb,
  assistantOrbState = null,
  modelLabel = "Assistant runtime",
  models = [],
  onSelectModel,
  contextInputTokens = 0,
  outputTokens = 0,
  totalTokens = 0,
  reasoningTokens = 0,
  contextWindow,
  cachedInputTokens = 0,
  reasoningEffort,
  reasoningEffortOptions = [],
  onSelectReasoningEffort,
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
          {messages.map((message, index) => {
            if (
              message.role === "assistant" &&
              !message.streaming &&
              !message.text.trim() &&
              !message.commentary?.length &&
              !message.stages?.length &&
              !message.directives?.length &&
              !message.activity?.length &&
              !message.approval &&
              !message.clarification
            ) {
              return null;
            }
            const visibleAssistantText = message.clarification ? "" : message.text;
            const messageId = message.id ?? `${message.role}-${index}`;
            return (
            <ChatbotMessage key={messageId} from={message.role}>
              {message.role === "assistant" ? (
                <ChatbotAssistantFrame orb={renderAssistantOrb(assistantOrbState)}>
                  <ChatbotMessageContent from="assistant">
                    <RichMessage text={visibleAssistantText} commentary={message.commentary} stages={message.stages} citations={message.citations} directives={message.directives} streaming={message.streaming} activity={message.activity} startedAt={message.activityStartedAt} endedAt={message.activityEndedAt} />
                    {message.approval ? (
                      <Confirmation
                        approval={message.approval.status === "pending" ? { id: message.approval.approvalId } : { id: message.approval.approvalId, approved: message.approval.status === "approved" }}
                        state={message.approval.status === "pending" ? "approval-requested" : "approval-responded"}
                        className="mt-3 rounded-lg border-border/70 bg-card/72 shadow-[var(--shadow-card)] backdrop-blur-xl"
                      >
                        <ConfirmationTitle>
                          {message.approval.status === "pending"
                            ? "Approval required before Marvex continues."
                            : message.approval.status === "approved"
                              ? "Approved."
                              : message.approval.status === "denied"
                                ? "Denied."
                                : "Approval cancelled."}
                        </ConfirmationTitle>
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
                        output={message.clarification.answerText ? { answer: { kind: "single", selectedIds: [message.clarification.options.find((option) => option.label === message.clarification?.answerText)?.id ?? ""], text: undefined } } : undefined}
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
                    {stripReasoning(message.text).trim() ? <ChatbotCopyAction text={stripReasoning(message.text)} /> : null}
                    {!message.streaming ? <ChatbotRetryAction onRetry={onRetryAssistantMessage ? () => void onRetryAssistantMessage(messageId) : undefined} /> : null}
                    {!message.streaming ? <ChatbotDeleteAction label="Delete response" onDelete={onDeleteMessage ? () => void onDeleteMessage(messageId) : undefined} /> : null}
                  </ChatbotMessageActions>
                </ChatbotAssistantFrame>
              ) : (
                <>
                  <ChatbotMessageContent from={message.role}>{message.text}</ChatbotMessageContent>
                  {message.role === "user" ? (
                    <ChatbotMessageActions className="mt-1">
                      <ChatbotEditAction onEdit={onEditUserMessage ? () => void onEditUserMessage(messageId, message.text) : undefined} />
                      <ChatbotDeleteAction onDelete={onDeleteMessage ? () => void onDeleteMessage(messageId) : undefined} />
                    </ChatbotMessageActions>
                  ) : null}
                </>
              )}
            </ChatbotMessage>
          );})}
          {pending && !messages.some((message) => message.role === "assistant" && message.streaming) ? (
            <ChatbotMessage from="assistant">
                <ChatbotAssistantFrame orb={renderAssistantOrb("thinking")}>
                  <ChatbotMessageContent from="assistant" className="text-muted-foreground">
                    <WorkTrace activity={[]} streaming startedAt={Date.now()} />
                  </ChatbotMessageContent>
                </ChatbotAssistantFrame>
            </ChatbotMessage>
          ) : null}
        </ChatbotConversationContent>
      </ChatbotConversation>
      <ChatbotScrollButton targetRef={conversationRef} />
      <div className="border-t border-border/30 bg-background/86 pt-3 backdrop-blur-xl">
        <ChatbotPromptInput
          disabled={pending}
          generating={pending}
          micActive={micActive}
          voiceSessionActive={voiceSessionActive}
          voiceSessionListening={voiceSessionListening}
          voiceSessionCue={voiceSessionCue}
          modelLabel={modelLabel}
          models={models}
          onSelectModel={onSelectModel}
          contextInputTokens={contextInputTokens}
          outputTokens={outputTokens}
          totalTokens={totalTokens}
          reasoningTokens={reasoningTokens}
          contextWindow={contextWindow}
          cachedInputTokens={cachedInputTokens}
          reasoningEffort={reasoningEffort}
          reasoningEffortOptions={reasoningEffortOptions}
          onSelectReasoningEffort={onSelectReasoningEffort}
          onStop={onStop}
          onSubmit={onSubmit}
          onToggleVoice={onToggleVoice}
          onToggleVoiceSession={onToggleVoiceSession}
          value={composerValue}
          onValueChange={onComposerValueChange}
        />
      </div>
    </section>
  );
}
