import { Component, lazy, Suspense, useEffect, useMemo, useRef, useState, useCallback, type ReactNode } from "react";
import { BrainCircuit, MessageSquare, Settings, Radio, History, X, Plus, Activity, ScrollText, Power, RotateCcw, Ear, Volume2, Pencil, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { listen } from "@/lib/tauriBridge";
import { type CitationRef, type TurnStage, type UiDirective } from "@/lib/localTurn";
import { cancelActiveChatTurn, cancelProviderResponse, deleteChatSession, deleteProviderResponse, getShellRuntimeConfig, renameChatSession, showOverlay, submitChatTurnStream, resumeApprovalTurn, startBackend, marvexShutdown, marvexRestart, createChatSession, listChatSessions, type BackendSession, type ChatStatusEvent, type ShellRuntimeConfig } from "@/lib/shellCommands";
import { getPersistedMode, persistMode } from "@/lib/modeStore";
import { displayDetail, idleAssistantState, normalizeAssistantState, type AssistantStateEvent, type AssistantStatusKind } from "@/lib/assistantState";
import { outcomeFromTurnResult, outcomeFromError, speechTextFromTurnResult } from "@/lib/turnOutcome";
import { providerResponseIdFromTurnResult } from "@/lib/turnResultHelpers";
import { deleteCachedSession, estimateSessionTokens, loadCachedMessages, renameCachedSession, saveCachedMessages, rememberSession, listCachedSessions, type SessionMeta, type StoredMessage } from "@/lib/sessionStore";
import { fetchProviders, refreshProviderModels, selectProviderModel, selectProviderReasoningEffort, type ProviderCatalog, type ProviderRow } from "@/lib/providerControlClient";
import { useBackendStatus, type WakewordState } from "@/lib/backendStatus";
import { fetchVoiceWorkerStatus, speakVoiceWorker, listenVoiceWorker, startVoiceWorker, transcriptFromStatus, voiceRejectionFromStatus, partialTranscriptFromStatus, wakeDetectionFromStatus, type VoiceWorkerStatus } from "@/lib/voiceControlClient";
import { runVoiceTurnWithSpeech } from "@/lib/voiceTurnSpeech";
import { voiceProgressSpeech, pickListeningCue } from "@/lib/voiceFillers";
import { activityLabel, type ActivityStep } from "@/lib/activityLabels";
import { addProviderUsage, emptyProviderUsage, providerUsageFromTurnResult, type ProviderUsage } from "@/lib/providerUsage";
import { MARVEX_APP_VERSION } from "@/lib/appVersion";

import { LimelightNav } from "@/components/dock";
import { Loader } from "@/components/loader";
import { ScrambleText } from "@/components/scramble-text";
import { BackgroundPlus } from "@/components/ui/background-plus";
import { MarvexChatShell, type MarvexChatClarification } from "@/components/chatbot-main/MarvexChatShell";
import { Status, StatusIndicator, StatusLabel } from "@/components/status-for-ui/status";
import { StartupScreen } from "@/components/marvex/StartupScreen";
import { StatusView } from "@/components/marvex/StatusView";
import { LogsView } from "@/components/marvex/LogsView";
import { VoiceMode } from "./VoiceMode";
import { ControlPlaneSettings } from "./ControlPlaneSettings";
import { MemorySettings } from "./MemorySettings";

type ChatApproval = { approvalId: string; traceId: string; turnId: string; text: string; status: "pending" | "approved" | "denied" | "cancelled" };
type ChatMessage = { id?: string; role: "user" | "assistant" | "system"; text: string; providerResponseId?: string; previousResponseId?: string; editedAt?: number; commentary?: string[]; stages?: TurnStage[]; citations?: CitationRef[]; directives?: UiDirective[]; approval?: ChatApproval; clarification?: MarvexChatClarification; streaming?: boolean; activity?: ActivityStep[]; activityStartedAt?: number; activityEndedAt?: number };
type TabId = "chat" | "voice" | "status" | "logs" | "memories" | "settings";
type AgentOrbState = "thinking" | "listening" | "talking" | null;
type SendResult = { text: string; speechText: string };
type VoiceCaptureTarget = "dictation" | "voice";
type WorkerTranscript = { text: string; eventId: string };

const NOISE_TRANSCRIPTS = new Set(["ah", "eh", "er", "huh", "hm", "hmm", "mm", "oh", "uh", "um", "umm"]);

let lastListeningCue = "";
function randomListeningCue(): string {
  const cue = pickListeningCue(lastListeningCue);
  lastListeningCue = cue;
  return cue;
}

function messageId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function lastProviderResponseId(messages: ChatMessage[]): string | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const id = messages[index]?.providerResponseId?.trim();
    if (id) return id;
  }
  return undefined;
}

// Restored sessions must never resume in a live "Working…" state: a turn that
// was interrupted mid-stream persists streaming=true, so settle it on load.
function restoreMessages(stored: StoredMessage[]): ChatMessage[] {
  return (stored as ChatMessage[]).map((message, index) => {
    const withId = { ...message, id: message.id ?? `restored-${index}` };
    return withId.role === "assistant" && withId.streaming
      ? { ...withId, streaming: false, activityEndedAt: withId.activityEndedAt ?? withId.activityStartedAt ?? Date.now() }
      : withId;
  });
}

function manualListenQueued(status: unknown): boolean {
  const events = (status as { recent_events?: Array<Record<string, unknown>> } | null | undefined)?.recent_events;
  if (!Array.isArray(events)) return false;
  const event = events[events.length - 1];
  const summary = event && typeof event === "object" ? (event as { summary?: Record<string, unknown> }).summary : undefined;
  return Boolean(summary?.manual_listen_queued);
}

function voiceTranscriptRejectReason(text: string): string | null {
  const stripped = text.replace(/\s+/g, " ").trim();
  if (!stripped) return "empty_transcript";
  const compact = stripped.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
  if (NOISE_TRANSCRIPTS.has(compact)) return "short_filler_or_noise";
  const words = stripped.replace(/[?!.,]+/g, " ").split(/\s+/).filter(Boolean);
  if (stripped.length <= 3 || (words.length === 1 && compact.length <= 3)) return "short_filler_or_noise";
  return null;
}

const LazyOrb = lazy(() => import("@/components/chat-messages-for-ui/agent-simple-orb").then((module) => ({ default: module.Orb })));

function agentStateFromStatus(status: AssistantStatusKind): AgentOrbState {
  if (status === "listening") return "listening";
  if (status === "talking") return "talking";
  if (status === "thinking" || status === "working" || status === "using_tools" || status === "mcp" || status === "skills" || status === "searching_web") return "thinking";
  return null;
}

const COMMENTARY_STATUSES = new Set(["thinking", "working", "using_tools", "mcp", "skills", "searching_web", "asking", "needs_approval"]);
const TURN_WORK_STATUSES = new Set<AssistantStatusKind>(["thinking", "working", "using_tools", "mcp", "skills", "searching_web"]);
const RESPONSES_REASONING_EFFORTS = new Set(["none", "minimal", "low", "medium", "high", "xhigh"]);

function statusActivityName(event: ChatStatusEvent): string | null {
  const status = String(event.status ?? "").trim();
  return COMMENTARY_STATUSES.has(status) ? `status.${status}` : null;
}

function modelRuntimeMetadata(provider: ProviderRow, model: string): {
  contextWindow?: number;
  reasoningEffort?: string;
  reasoningEffortOptions: string[];
} {
  const metadata = metadataForModel(provider, model);
  const supportsReasoning = metadata?.supports_reasoning === true;
  const metadataOptions = normalizeReasoningOptions(metadata?.reasoning_effort_options);
  const current = normalizeReasoningEffort(provider.reasoning_effort);
  const fallback = supportsReasoning && metadataOptions.length === 0 ? ["none", "low", "medium", "high"] : [];
  const options = dedupeStrings([...metadataOptions, ...fallback, ...(supportsReasoning && current ? [current] : [])]);
  return {
    contextWindow: metadata?.context_window,
    reasoningEffort: current || options[0],
    reasoningEffortOptions: options,
  };
}

function metadataForModel(provider: ProviderRow, model: string): NonNullable<ProviderRow["model_metadata"]>[string] | undefined {
  const metadata = provider.model_metadata;
  if (!metadata) return undefined;
  if (metadata[model]) return metadata[model];
  const lowered = model.toLowerCase();
  const exactCase = Object.entries(metadata).find(([key]) => key.toLowerCase() === lowered)?.[1];
  if (exactCase) return exactCase;
  const tail = lowered.split("/").pop();
  if (!tail) return undefined;
  return Object.entries(metadata).find(([key]) => key.toLowerCase().split("/").pop() === tail)?.[1];
}

function normalizeReasoningOptions(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  return dedupeStrings(values.map((value) => normalizeReasoningEffort(value)).filter(Boolean));
}

function normalizeReasoningEffort(value: unknown): string {
  const cleaned = String(value ?? "").trim().toLowerCase();
  const aliases: Record<string, string> = {
    off: "none",
    on: "medium",
    max: "xhigh",
  };
  const normalized = aliases[cleaned] ?? cleaned;
  return RESPONSES_REASONING_EFFORTS.has(normalized) ? normalized : "";
}

function dedupeStrings(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function idleStateNow(): AssistantStateEvent {
  return { ...idleAssistantState, ts: new Date().toISOString() };
}

export function ChatApp() {
  const [config, setConfig] = useState<ShellRuntimeConfig | null>(null);
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const sessionIdRef = useRef<string | null>(null);
  const previousResponseIdsRef = useRef<Record<string, string>>({});
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "system", text: "Marvex is ready." }]);
  const [sessions, setSessions] = useState<SessionMeta[]>(() => listCachedSessions());
  const [providers, setProviders] = useState<ProviderCatalog | null>(null);
  const [providerUsage, setProviderUsage] = useState<ProviderUsage>({ ...emptyProviderUsage });
  const [pending, setPending] = useState(false);
  const [dictationActive, setDictationActive] = useState(false);
  const [composerText, setComposerText] = useState("");
  const [voiceSessionActive, setVoiceSessionActive] = useState(false);
  const [voiceSessionListening, setVoiceSessionListening] = useState(false);
  const [voiceSessionCue, setVoiceSessionCue] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("chat");

  const backend = useBackendStatus();
  const [helloDone, setHelloDone] = useState(false);
  const [booted, setBooted] = useState(false);
  const messagesRef = useRef<ChatMessage[]>(messages);
  const voiceSessionActiveRef = useRef(false);
  const pendingRef = useRef(false);
  const voiceListenPendingRef = useRef(false);
  const voiceCaptureTargetRef = useRef<VoiceCaptureTarget | null>(null);
  const manualVoiceCuePlayedRef = useRef(false);
  const lastWakeCueEventRef = useRef("");
  const voiceSessionGenerationRef = useRef(0);
  const ignoreNextVoiceTranscriptRef = useRef(false);
  const requestVoiceListenRef = useRef<(withCue?: boolean, generation?: number) => void>(() => undefined);

  const activateBackendSession = useCallback((session: BackendSession) => {
    const id = session.session_ref.ref_id;
    sessionIdRef.current = id;
    const cached = listCachedSessions().find((item) => item.id === id);
    if (cached?.lastProviderResponseId) previousResponseIdsRef.current[id] = cached.lastProviderResponseId;
    rememberSession({ id, title: session.title, updatedAt: session.updated_at_unix_ms });
    const restored = restoreMessages(loadCachedMessages(id));
    setMessages(restored.length ? restored : [{ role: "system", text: "Marvex is ready." }]);
    setProviderUsage(cached?.providerUsage ?? { ...emptyProviderUsage });
    setSessions(listCachedSessions());
  }, []);

  const ensureBackendSession = useCallback(async (): Promise<string> => {
    if (sessionIdRef.current) return sessionIdRef.current;
    const first = (await listChatSessions()).sessions[0] ?? (await createChatSession("New chat")).session;
    activateBackendSession(first);
    return first.session_ref.ref_id;
  }, [activateBackendSession]);

  useEffect(() => {
    void getShellRuntimeConfig().then(setConfig).catch(() => setConfig(null));
    let cleanup: VoidFunction | undefined;
    void listen("assistant-state", (event) => {
      try {
        const next = normalizeAssistantState(event.payload);
        if (!pendingRef.current && TURN_WORK_STATUSES.has(next.status)) return;
        setState(next);
      }
      catch { setState(idleAssistantState); }
    }).then((unlisten) => { cleanup = unlisten; });
    return () => cleanup?.();
  }, []);

  // Load the provider catalog once the control plane is reachable, and keep
  // retrying until it lands. Fetching only once on mount raced the runtime
  // starting up: a single early failure left `providers` null forever, which
  // showed as an endless "Connecting runtime" in the model selector.
  useEffect(() => {
    if (providers) return;
    let active = true;
    const attempt = () =>
      fetchProviders()
        .then((catalog) => {
          if (!active) return undefined;
          setProviders(catalog);
          return refreshProviderModels(catalog.active_provider_id);
        })
        .then((refreshed) => { if (active && refreshed) setProviders(refreshed); })
        .catch(() => undefined);
    void attempt();
    const timer = window.setInterval(() => { if (active) void attempt(); }, 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, [providers, backend?.ready]);

  useEffect(() => {
    if (!backend?.ready || sessionIdRef.current) return;
    void listChatSessions()
      .then(async (response) => {
        const first = response.sessions[0] ?? (await createChatSession("New chat")).session;
        activateBackendSession(first);
      })
      .catch(() => undefined);
  }, [backend?.ready, activateBackendSession]);

  // Reveal chat once backend is ready AND the hello has played (hello always
  // plays on open).
  useEffect(() => {
    if (backend?.ready && helloDone && !booted) {
      const t = setTimeout(() => setBooted(true), 350);
      return () => clearTimeout(t);
    }
  }, [backend?.ready, helloDone, booted]);

  useEffect(() => {
    messagesRef.current = messages;
    if (sessionIdRef.current) {
      saveCachedMessages(sessionIdRef.current, messages as StoredMessage[]);
      setSessions(listCachedSessions());
    }
  }, [messages]);

  // Replace the last (in-progress) assistant bubble; used for streaming deltas
  // and final reconciliation so we never append a duplicate assistant message.
  const updateLastAssistant = useCallback((patch: ChatMessage) => {
    setMessages((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === "assistant") {
          next[i] = { ...next[i], ...patch };
          messagesRef.current = next;
          return next;
        }
      }
      next.push({ ...patch, id: patch.id ?? messageId("assistant") });
      messagesRef.current = next;
      return next;
    });
  }, []);

  const lastVoiceEventRef = useRef<string>("");
  const lastNonEnglishNoticeRef = useRef<string>("");
  // Tracks the live streaming partial we last previewed in the composer, so we
  // only overwrite/clear our own preview and never clobber text the user typed.
  const lastPartialRef = useRef<string>("");

  const send = useCallback(async (text: string, options: { appendUser?: boolean; previousResponseId?: string; onProgress?: (text: string) => void } = {}): Promise<SendResult> => {
    if (!text.trim() || pendingRef.current) return { text: "", speechText: "" };
    const appendUser = options.appendUser ?? true;
    pendingRef.current = true;
    setPending(true);
    // Timer anchor for the "Working…/Worked for …" trace.
    const startedAt = Date.now();
    const userMessageId = messageId("user");
    const assistantMessageId = messageId("assistant");
    let turnPreviousResponseId = options.previousResponseId;
    // Append a user message only for direct user turns. Follow-up UI controls
    // such as clarification answers and approvals update the active assistant
    // turn instead of creating transcript noise.
    let turnPlaceholderAppended = false;
    const appendTurnPlaceholder = () => {
      if (turnPlaceholderAppended) return;
      turnPlaceholderAppended = true;
      if (appendUser) {
        setMessages((prev) => [...prev, { id: userMessageId, role: "user", text, previousResponseId: turnPreviousResponseId }, { id: assistantMessageId, role: "assistant", text: "", previousResponseId: turnPreviousResponseId, streaming: true, activityStartedAt: startedAt }]);
      } else {
        updateLastAssistant({ id: assistantMessageId, role: "assistant", text: "", previousResponseId: turnPreviousResponseId, streaming: true, activityStartedAt: startedAt });
      }
    };
    let replyText = "";
    let speechText = "";
    let streamed = "";
    let activity: ActivityStep[] = [];
    let commentary: string[] = [];
    let modelCommentarySeen = false;
    try {
      const sessionId = await ensureBackendSession();
      turnPreviousResponseId = options.previousResponseId ?? previousResponseIdsRef.current[sessionId];
      appendTurnPlaceholder();
      const result = await submitChatTurnStream(
        text,
        { session_id: sessionId },
        turnPreviousResponseId,
        {
          onDelta: (chunk) => {
            streamed += chunk;
            updateLastAssistant({ id: assistantMessageId, role: "assistant", text: streamed, commentary, previousResponseId: turnPreviousResponseId, streaming: true, activity, activityStartedAt: startedAt });
          },
          onResponse: (responseId) => {
            updateLastAssistant({ id: assistantMessageId, role: "assistant", text: streamed, providerResponseId: responseId, commentary, previousResponseId: turnPreviousResponseId, streaming: true, activity, activityStartedAt: startedAt });
          },
          onTool: (event) => {
            const id = event.id || event.name || String(activity.length);
            if (event.phase === "end") {
              activity = activity.map((step) => (step.id === id || step.name === event.name) && step.active ? { ...step, active: false } : step);
            } else {
              const step = { id, name: event.name ?? "", arguments: event.arguments, active: true };
              activity = [...activity, step];
              if (!modelCommentarySeen) options.onProgress?.(activityLabel(step));
            }
            updateLastAssistant({ id: assistantMessageId, role: "assistant", text: streamed, commentary, previousResponseId: turnPreviousResponseId, streaming: true, activity, activityStartedAt: startedAt });
          },
          onStatus: (event) => {
            const name = statusActivityName(event);
            activity = activity.map((step) => step.name.startsWith("status.") && step.active ? { ...step, active: false } : step);
            if (name && activity[activity.length - 1]?.name !== name) {
              const step = { id: `${name}:${activity.length}`, name, active: true };
              activity = [...activity, step];
              if (!modelCommentarySeen) options.onProgress?.(activityLabel(step));
            }
            updateLastAssistant({ id: assistantMessageId, role: "assistant", text: streamed, commentary, previousResponseId: turnPreviousResponseId, streaming: true, activity, activityStartedAt: startedAt });
          },
          onCommentary: (event) => {
            const modelText = String(event.text ?? "").trim();
            if (!modelText || commentary.includes(modelText)) return;
            modelCommentarySeen = true;
            commentary = [...commentary, modelText];
            if (streamed.trim() === modelText) streamed = "";
            options.onProgress?.(modelText);
            updateLastAssistant({ id: assistantMessageId, role: "assistant", text: streamed, commentary, previousResponseId: turnPreviousResponseId, streaming: true, activity, activityStartedAt: startedAt });
          },
        },
      );
      const nextProviderResponseId = providerResponseIdFromTurnResult(result);
      if (nextProviderResponseId) {
        previousResponseIdsRef.current[sessionId] = nextProviderResponseId;
        const cached = listCachedSessions().find((item) => item.id === sessionId);
        rememberSession({
          id: sessionId,
          title: (cached?.title ?? text.slice(0, 48)) || "New chat",
          updatedAt: Date.now(),
          lastProviderResponseId: nextProviderResponseId,
        });
      }
      const outcome = outcomeFromTurnResult(result);
      const turnUsage = providerUsageFromTurnResult(result);
      setProviderUsage((current) => {
        const cumulative = addProviderUsage(current, turnUsage);
        const cached = listCachedSessions().find((item) => item.id === sessionId);
        const anchor = nextProviderResponseId ?? previousResponseIdsRef.current[sessionId];
        const sessionPatch: SessionMeta = {
          id: sessionId,
          title: (cached?.title ?? text.slice(0, 48)) || "New chat",
          updatedAt: Date.now(),
          providerUsage: cumulative,
        };
        if (anchor) sessionPatch.lastProviderResponseId = anchor;
        rememberSession(sessionPatch);
        return cumulative;
      });
      replyText = outcome.text;
      speechText = speechTextFromTurnResult(result);
      // Reconcile with the authoritative final result (text + stages + refs).
      // Settle any still-active tool steps so the chain-of-thought stops shimmering.
      const settledActivity = activity.map((step) => (step.active ? { ...step, active: false } : step));
      updateLastAssistant({ id: assistantMessageId, role: "assistant", text: outcome.text, providerResponseId: nextProviderResponseId, previousResponseId: turnPreviousResponseId, commentary: commentary.length ? commentary : undefined, stages: outcome.stages, citations: outcome.citations, directives: outcome.directives, approval: approvalFromTurnResult(result, text), clarification: clarificationFromTurnResult(result, text), activity: settledActivity.length ? settledActivity : undefined, activityStartedAt: startedAt, activityEndedAt: Date.now() });
    } catch (error) {
      appendTurnPlaceholder();
      const outcome = outcomeFromError(error);
      replyText = outcome.text;
      updateLastAssistant({ id: assistantMessageId, role: "assistant", text: outcome.text, previousResponseId: turnPreviousResponseId, activityStartedAt: startedAt, activityEndedAt: Date.now() });
    } finally {
      pendingRef.current = false;
      setPending(false);
      setState(idleStateNow());
    }
    return { text: replyText, speechText };
  }, [ensureBackendSession, updateLastAssistant]);

  const answerClarification = useCallback((clarification: MarvexChatClarification, answerText: string) => {
    const reply = answerText.trim();
    if (!reply) return;
    setMessages((prev) => prev.map((message) => {
      if (message.clarification?.originalText !== clarification.originalText) return message;
      return {
        ...message,
        clarification: { ...message.clarification, answerText: reply },
      };
    }));
    // Re-ask the original question with the disambiguation so the backend
    // resolves it (and the spaced "open ai" trigger no longer fires).
    const composed = clarification.originalText.trim()
      ? `${clarification.originalText.trim()} (I mean: ${reply})`
      : reply;
    void send(composed, { appendUser: true });
  }, [send]);

  const stopChatTurn = useCallback(() => {
    const activeResponseId = [...messagesRef.current]
      .reverse()
      .find((message) => message.role === "assistant" && message.streaming && message.providerResponseId)?.providerResponseId;
    void cancelActiveChatTurn().catch(() => undefined);
    if (activeResponseId) void cancelProviderResponse(activeResponseId).catch(() => undefined);
    pendingRef.current = false;
    setPending(false);
    setState(idleStateNow());
    setMessages((prev) => prev.filter((message) => !(message.role === "assistant" && !message.text.trim() && message.streaming)));
  }, []);

  const decideChatApproval = useCallback(async (approval: ChatApproval, decision: "approve" | "deny" | "cancel") => {
    setPending(true);
    try {
      const result = await resumeApprovalTurn({
        text: approval.text,
        traceId: approval.traceId,
        turnId: approval.turnId,
        approvalId: approval.approvalId,
        decision,
      });
      const outcome = outcomeFromTurnResult(result);
      setMessages((prev) => prev.map((message) => {
        if (message.approval?.approvalId !== approval.approvalId) return message;
        return {
          ...message,
          approval: {
            ...message.approval,
            status: decision === "approve" ? "approved" : decision === "cancel" ? "cancelled" : "denied",
          },
          text: outcome.text,
          stages: outcome.stages ?? message.stages,
          directives: outcome.directives ?? message.directives,
        };
      }));
    } catch (error) {
      const outcome = outcomeFromError(error);
      setMessages((prev) => [...prev, { role: "assistant", text: outcome.text }]);
    } finally {
      setPending(false);
      setState(idleStateNow());
    }
  }, []);

  const syncSessionResponseAnchor = useCallback((nextMessages: ChatMessage[]) => {
    const sessionId = sessionIdRef.current;
    if (!sessionId) return;
    const nextResponseId = lastProviderResponseId(nextMessages);
    if (nextResponseId) {
      previousResponseIdsRef.current[sessionId] = nextResponseId;
    } else {
      delete previousResponseIdsRef.current[sessionId];
    }
    const cached = listCachedSessions().find((item) => item.id === sessionId);
    rememberSession({
      id: sessionId,
      title: cached?.title ?? nextMessages.find((message) => message.role === "user")?.text.slice(0, 48) ?? "New chat",
      updatedAt: Date.now(),
      lastProviderResponseId: nextResponseId,
    });
  }, []);

  const deleteMessage = useCallback((messageId: string) => {
    if (pendingRef.current) return;
    const current = messagesRef.current;
    const index = current.findIndex((message) => message.id === messageId);
    if (index < 0) return;
    const target = current[index];
    let removeThrough = index;
    if (target.role === "user" && current[index + 1]?.role === "assistant") removeThrough = index + 1;
    const removed = current.slice(index, removeThrough + 1);
    const next = [...current.slice(0, index), ...current.slice(removeThrough + 1)];
    messagesRef.current = next;
    setMessages(next);
    syncSessionResponseAnchor(next);
    for (const message of removed) {
      if (message.providerResponseId) void deleteProviderResponse(message.providerResponseId).catch(() => undefined);
    }
  }, [syncSessionResponseAnchor]);

  const editUserMessage = useCallback((messageId: string, currentText: string) => {
    if (pendingRef.current) return;
    const edited = window.prompt("Edit message", currentText)?.trim();
    if (!edited || edited === currentText.trim()) return;
    const current = messagesRef.current;
    const index = current.findIndex((message) => message.id === messageId && message.role === "user");
    if (index < 0) return;
    const previousResponseId = current[index].previousResponseId;
    const removedAssistantResponseIds = current.slice(index).flatMap((message) => message.providerResponseId ? [message.providerResponseId] : []);
    const next = current.slice(0, index);
    messagesRef.current = next;
    setMessages(next);
    syncSessionResponseAnchor(next);
    for (const responseId of removedAssistantResponseIds) void deleteProviderResponse(responseId).catch(() => undefined);
    void send(edited, { appendUser: true, previousResponseId });
  }, [send, syncSessionResponseAnchor]);

  const retryAssistantMessage = useCallback((messageId: string) => {
    if (pendingRef.current) return;
    let retryText = "";
    let previousResponseId: string | undefined;
    const current = messagesRef.current;
    const index = current.findIndex((message) => message.id === messageId && message.role === "assistant");
    if (index < 0) return;
    for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
      if (current[cursor].role === "user") {
        retryText = current[cursor].text;
        previousResponseId = current[cursor].previousResponseId;
        break;
      }
    }
    if (!retryText.trim()) return;
    const removedResponseIds = current.slice(index).flatMap((message) => message.providerResponseId ? [message.providerResponseId] : []);
    const next = current.slice(0, index);
    messagesRef.current = next;
    setMessages(next);
    syncSessionResponseAnchor(next);
    for (const responseId of removedResponseIds) void deleteProviderResponse(responseId).catch(() => undefined);
    void send(retryText, { appendUser: false, previousResponseId });
  }, [send, syncSessionResponseAnchor]);

  const stopManualVoiceSession = useCallback(() => {
    voiceSessionGenerationRef.current += 1;
    ignoreNextVoiceTranscriptRef.current = true;
    voiceSessionActiveRef.current = false;
    voiceListenPendingRef.current = false;
    manualVoiceCuePlayedRef.current = false;
    if (voiceCaptureTargetRef.current === "voice") voiceCaptureTargetRef.current = null;
    setVoiceSessionActive(false);
    setVoiceSessionListening(false);
    setVoiceSessionCue("");
  }, []);

  const handleVoiceTranscript = useCallback(async (text: string, options: { shouldSpeak?: () => boolean } = {}) => {
    // Voice mode speaks live progress. Swap content-free status labels
    // ("Thinking", "Working") for a single playful filler and stay quiet for the
    // rest, while the on-screen activity chips keep their precise labels.
    const voiceProgress = { fillerSpoken: false, previousFiller: "" };
    await runVoiceTurnWithSpeech({
      runTurn: (reportProgress) =>
        send(text, {
          onProgress: (label) => {
            const speech = voiceProgressSpeech(label, voiceProgress);
            if (speech.skip) return;
            if (speech.isFiller) {
              voiceProgress.fillerSpoken = true;
              voiceProgress.previousFiller = speech.text;
            }
            reportProgress(speech.text);
          },
        }),
      speechText: (reply) => reply.speechText,
      speak: speakVoiceWorker,
      shouldSpeak: options.shouldSpeak,
    });
  }, [send]);

  // When the language gate drops a non-English utterance, the turn produces no
  // transcript and nothing happens — speak a brief one-time notice so the silence
  // isn't confusing. Deduped per worker event so it never repeats or spams.
  const maybeNoticeNonEnglish = useCallback((status: VoiceWorkerStatus | null | undefined) => {
    const rejection = voiceRejectionFromStatus(status);
    if (!rejection || rejection.reason !== "non_english_ignored") return;
    if (rejection.eventId === lastNonEnglishNoticeRef.current) return;
    lastNonEnglishNoticeRef.current = rejection.eventId;
    void speakVoiceWorker("Sorry, I only understand English right now.", { bargeIn: false }).catch(() => undefined);
  }, []);

  const consumeVoiceTranscript = useCallback(async (transcript: WorkerTranscript): Promise<boolean> => {
    if (transcript.eventId === lastVoiceEventRef.current) return false;
    lastVoiceEventRef.current = transcript.eventId;
    const target = voiceCaptureTargetRef.current;
    const rejectReason = voiceTranscriptRejectReason(transcript.text);
    if (target === "dictation") {
      if (rejectReason) {
        setDictationActive(false);
        voiceCaptureTargetRef.current = null;
        return false;
      }
      setComposerText((current) => {
        // Drop our streaming preview before folding in the final text.
        const base = current === lastPartialRef.current ? "" : current;
        return [base.trim(), transcript.text].filter(Boolean).join(" ");
      });
      lastPartialRef.current = "";
      setDictationActive(false);
      voiceCaptureTargetRef.current = null;
      return true;
    }
    // Sent voice turns: clear our streaming preview so the words don't linger in
    // the box after the message is sent.
    setComposerText((cur) => (cur === lastPartialRef.current ? "" : cur));
    lastPartialRef.current = "";
    if (target === "voice") {
      const generation = voiceSessionGenerationRef.current;
      const stillCurrent = () => voiceSessionGenerationRef.current === generation;
      setVoiceSessionListening(false);
      voiceListenPendingRef.current = false;
      voiceCaptureTargetRef.current = null;
      if (rejectReason) {
        stopManualVoiceSession();
        return false;
      }
      await handleVoiceTranscript(transcript.text, { shouldSpeak: stillCurrent });
      if (stillCurrent()) {
        window.setTimeout(() => requestVoiceListenRef.current(false, generation), 250);
      }
      return true;
    }
    if (ignoreNextVoiceTranscriptRef.current) {
      ignoreNextVoiceTranscriptRef.current = false;
      return false;
    }
    if (rejectReason) return false;
    await handleVoiceTranscript(transcript.text);
    return true;
  }, [handleVoiceTranscript, stopManualVoiceSession]);

  const requestVoiceListen = useCallback(async (withCue = false, generation = voiceSessionGenerationRef.current) => {
    const stillCurrent = () => voiceSessionActiveRef.current && voiceSessionGenerationRef.current === generation;
    if (voiceListenPendingRef.current || pending || !stillCurrent()) return;
    voiceListenPendingRef.current = true;
    voiceCaptureTargetRef.current = "voice";
    setVoiceSessionListening(true);
    if (withCue && !manualVoiceCuePlayedRef.current) {
      const cue = randomListeningCue();
      manualVoiceCuePlayedRef.current = true;
      setVoiceSessionCue(cue);
      await speakVoiceWorker(cue, { bargeIn: false }).catch(() => undefined);
      if (!stillCurrent()) {
        voiceListenPendingRef.current = false;
        if (voiceCaptureTargetRef.current === "voice") voiceCaptureTargetRef.current = null;
        setVoiceSessionListening(false);
        return;
      }
    }
    try {
      const status = await listenVoiceWorker();
      if (!stillCurrent()) {
        voiceListenPendingRef.current = false;
        if (voiceCaptureTargetRef.current === "voice") voiceCaptureTargetRef.current = null;
        setVoiceSessionListening(false);
        return;
      }
      const transcript = transcriptFromStatus(status);
      if (transcript) {
        await consumeVoiceTranscript(transcript);
        return;
      }
      maybeNoticeNonEnglish(status);
      if (manualListenQueued(status)) return;
      voiceListenPendingRef.current = false;
      voiceCaptureTargetRef.current = null;
      setVoiceSessionListening(false);
    } catch {
      voiceListenPendingRef.current = false;
      voiceCaptureTargetRef.current = null;
      setVoiceSessionListening(false);
    }
  }, [consumeVoiceTranscript, maybeNoticeNonEnglish, pending]);

  useEffect(() => {
    requestVoiceListenRef.current = (withCue = false, generation = voiceSessionGenerationRef.current) => {
      void requestVoiceListen(withCue, generation);
    };
  }, [requestVoiceListen]);

  const toggleDictation = useCallback(() => {
    if (dictationActive || pending) return;
    setDictationActive(true);
    voiceCaptureTargetRef.current = "dictation";
    void listenVoiceWorker()
      .then(async (status) => {
        const transcript = transcriptFromStatus(status);
        if (transcript) {
          await consumeVoiceTranscript(transcript);
          return;
        }
        maybeNoticeNonEnglish(status);
        if (manualListenQueued(status)) return;
        setDictationActive(false);
        if (voiceCaptureTargetRef.current === "dictation") voiceCaptureTargetRef.current = null;
      })
      .catch(() => {
        setDictationActive(false);
        if (voiceCaptureTargetRef.current === "dictation") voiceCaptureTargetRef.current = null;
      });
  }, [consumeVoiceTranscript, maybeNoticeNonEnglish, dictationActive, pending]);

  const toggleVoiceSession = useCallback(() => {
    if (voiceSessionActiveRef.current) {
      stopManualVoiceSession();
      return;
    }
    const generation = voiceSessionGenerationRef.current + 1;
    voiceSessionGenerationRef.current = generation;
    voiceSessionActiveRef.current = true;
    voiceListenPendingRef.current = false;
    manualVoiceCuePlayedRef.current = false;
    setVoiceSessionCue("");
    setVoiceSessionActive(true);
    void startVoiceWorker()
      .catch(() => undefined)
      .finally(() => requestVoiceListenRef.current(true, generation));
  }, [stopManualVoiceSession]);

  // Voice loop bridge (docs/TODO/04): poll the worker for a freshly recognized
  // transcript, run it as a chat turn, and speak the reply back through the
  // worker. The worker handles wake -> capture -> STT and emits normalized text;
  // the shell mediates turn + speak because the worker is loopback-isolated from
  // Core. This must run for background wake-word transcripts and queued manual
  // listens too: if we only polled while the composer mic is active, "Hey
  // Marvex" or a queued dictation capture could transcribe but never reach the
  // UI.
  const wakewordActive = backend?.wakeword === "enabled" || backend?.wakeword === "running";
  const voiceBridgeActive = dictationActive || wakewordActive || voiceSessionActive;
  useEffect(() => {
    if (!voiceBridgeActive) return;
    let cancelled = false;
    let busy = false;
    const timer = setInterval(() => {
      if (busy) return;
      if (getPersistedMode() !== "chat") return;
      busy = true;
      void Promise.resolve(fetchVoiceWorkerStatus())
        .then(async (status) => {
          if (cancelled) return;
          const transcript = transcriptFromStatus(status);
          if (!transcript) {
            const wake = wakeDetectionFromStatus(status);
            if (wake?.eventId && wake.eventId !== lastWakeCueEventRef.current) {
              lastWakeCueEventRef.current = wake.eventId;
              const cue = randomListeningCue();
              setVoiceSessionCue(cue);
              void speakVoiceWorker(cue, { bargeIn: false }).catch(() => undefined);
            }
            // Preview the live streaming partial in the composer so the user sees
            // their words appear while speaking. Only overwrite our own preview
            // (or an empty box) so typed text is never clobbered.
            const partial = partialTranscriptFromStatus(status);
            if (partial) {
              setComposerText((cur) => (cur === "" || cur === lastPartialRef.current ? partial : cur));
              lastPartialRef.current = partial;
            }
            maybeNoticeNonEnglish(status);
            return;
          }
          await consumeVoiceTranscript(transcript);
        })
        .catch(() => undefined)
        .finally(() => {
          busy = false;
        });
    }, 700);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [consumeVoiceTranscript, maybeNoticeNonEnglish, voiceBridgeActive]);

  const navItems = useMemo(() => [
    { id: "chat" as TabId, icon: <MessageSquare />, label: "Chat", onClick: () => setActiveTab("chat") },
    { id: "voice" as TabId, icon: <Volume2 />, label: "Voice Mode", onClick: () => setActiveTab("voice") },
    { id: "status" as TabId, icon: <Activity />, label: "Status", onClick: () => setActiveTab("status") },
    { id: "logs" as TabId, icon: <ScrollText />, label: "Logs", onClick: () => setActiveTab("logs") },
    { id: "memories" as TabId, icon: <BrainCircuit />, label: "Memories", onClick: () => setActiveTab("memories") },
    { id: "settings" as TabId, icon: <Settings />, label: "Settings", onClick: () => setActiveTab("settings") },
  ], []);
  const activeNavIndex = Math.max(0, navItems.findIndex((n) => n.id === activeTab));

  const startNewSession = useCallback(() => {
    void createChatSession("New chat").then(({ session }) => {
      activateBackendSession(session);
      delete previousResponseIdsRef.current[session.session_ref.ref_id];
      setMessages([{ role: "system", text: "New chat started." }]);
      setSidebarOpen(false);
      setActiveTab("chat");
    }).catch(() => undefined);
  }, []);

  const renameSession = useCallback((session: SessionMeta) => {
    const title = window.prompt("Rename chat", session.title || "New chat")?.trim();
    if (!title) return;
    renameCachedSession(session.id, title);
    setSessions(listCachedSessions());
    void renameChatSession(session.id, title).catch(() => undefined);
  }, []);

  const removeSession = useCallback((session: SessionMeta) => {
    deleteCachedSession(session.id);
    setSessions(listCachedSessions());
    void deleteChatSession(session.id).catch(() => undefined);
    if (session.id === sessionIdRef.current) {
      sessionIdRef.current = null;
      setMessages([{ role: "system", text: "Marvex is ready." }]);
    }
  }, []);

  const modelOptions = useMemo(() => {
    const rows = providers?.providers ?? [];
    return rows.flatMap((provider) => {
      const models = Array.from(new Set([
        provider.active_model,
        ...(provider.models ?? []),
      ].filter((model): model is string => Boolean(model?.trim()))));
      return models.map((model) => ({
        ...modelRuntimeMetadata(provider, model),
        id: `${provider.provider_id}:${model}`,
        name: model,
        provider: provider.provider_id.split("_")[0],
        active: provider.provider_id === providers?.active_provider_id && model === provider.active_model,
        providerId: provider.provider_id,
        model,
      }));
    });
  }, [providers]);

  // The displayed/active model is derived straight from the catalog's active
  // provider row, not just from whichever option happens to carry the `active`
  // flag. That keeps the header from falling back to "Select model" during the
  // mount-time refresh window (or any option-list mismatch) when a model IS in
  // fact selected.
  const activeModelOption = useMemo(() => {
    const flagged = modelOptions.find((model) => model.active);
    if (flagged) return flagged;
    const activeProvider = providers?.providers.find((provider) => provider.provider_id === providers.active_provider_id);
    const activeModel = activeProvider?.active_model?.trim();
    if (!activeProvider || !activeModel) return undefined;
    return {
      ...modelRuntimeMetadata(activeProvider, activeModel),
      id: `${activeProvider.provider_id}:${activeModel}`,
      name: activeModel,
      provider: activeProvider.provider_id.split("_")[0],
      active: true,
      providerId: activeProvider.provider_id,
      model: activeModel,
    };
  }, [modelOptions, providers]);

  const selectModel = useCallback((value: string) => {
    const found = modelOptions.find((model) => model.id === value);
    if (!found) return;
    void selectProviderModel(found.providerId, found.model).then(setProviders).catch(() => undefined);
  }, [modelOptions]);

  const selectReasoningEffort = useCallback((effort: string) => {
    const active = activeModelOption;
    if (!active) return;
    void selectProviderReasoningEffort(active.providerId, effort).then(setProviders).catch(() => undefined);
  }, [activeModelOption]);

  const openSession = useCallback((id: string) => {
    sessionIdRef.current = id;
    const cached = listCachedSessions().find((item) => item.id === id);
    if (cached?.lastProviderResponseId) {
      previousResponseIdsRef.current[id] = cached.lastProviderResponseId;
    } else {
      delete previousResponseIdsRef.current[id];
    }
    const restored = restoreMessages(loadCachedMessages(id));
    setMessages(restored.length ? restored : [{ role: "system", text: "Marvex is ready." }]);
    setProviderUsage(cached?.providerUsage ?? { ...emptyProviderUsage });
    setSidebarOpen(false);
    setActiveTab("chat");
  }, []);

  const orbState = agentStateFromStatus(state.status);

  if (!booted) {
    return <StartupScreen backend={backend} onHelloDone={() => setHelloDone(true)} onRetry={() => void startBackend().catch(() => undefined)} />;
  }

  const TAB_TITLES: Record<TabId, string> = { chat: "Assistant Chat", voice: "Voice Mode", status: "Status", logs: "Logs / Traces / Telemetry", memories: "Memories", settings: "Settings" };
  const activeSession = sessions.find((session) => session.id === sessionIdRef.current);
  const headerSubtitle = activeTab === "chat"
    ? `${activeSession?.title || "Current chat"} • ${backend?.phase ?? "runtime"}`
    : `${backend?.ready ? "Core connected" : "Core starting"} • ${backend?.phase ?? "runtime"}`;

  return (
    <div className="marvex-chat-shell flex flex-col h-screen min-h-0 relative z-[1]">
      <header className="marvex-chat-header">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => setSidebarOpen((v) => !v)} title="Sessions" style={iconBtn}><History size={16} /></button>
          <img src="/assets/Marvex_App_192.png" alt="Marvex" style={{ width: 30, height: 30, borderRadius: 8, objectFit: "contain" }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <ScrambleText as="h1" text={TAB_TITLES[activeTab]} className="m-0 text-[17px] font-bold" style={{ color: "var(--foreground)" }} />
              <span
                aria-label="Marvex version"
                title="Marvex version"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  height: 18,
                  borderRadius: 999,
                  border: "1px solid color-mix(in srgb, var(--border) 70%, transparent)",
                  background: "color-mix(in srgb, var(--secondary) 74%, transparent)",
                  color: "var(--muted-foreground)",
                  padding: "0 7px",
                  fontSize: 10,
                  fontWeight: 650,
                  lineHeight: "18px",
                  letterSpacing: 0,
                }}
              >
                v{MARVEX_APP_VERSION}
              </span>
            </div>
            <p style={{ margin: "1px 0 0", color: "var(--muted-foreground)", fontSize: 11 }}>{config ? headerSubtitle : "Connecting runtime..."}</p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <WakewordBadge state={backend?.wakeword ?? "unknown"} />
          {(pending || state.status !== "idle") && <Loader variant="circular" size="sm" />}
          <Status status={state.status === "idle" ? "online" : "degraded"}>
            <StatusIndicator />
            <StatusLabel>{state.status === "idle" ? "Ready" : displayDetail(state)}</StatusLabel>
          </Status>
          <div style={{ width: 1, height: 24, background: "var(--border)" }} />
          <button onClick={() => void marvexRestart()} title="Restart Marvex" style={iconBtn}><RotateCcw size={15} /></button>
          <button onClick={() => void marvexShutdown()} title="Shutdown Marvex" style={{ ...iconBtn, color: "var(--destructive)" }}><Power size={15} /></button>
        </div>
      </header>

      <div style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", position: "relative", background: "var(--sidebar)", padding: "0 0 0 0" }}>
        <AnimatePresence>
          {sidebarOpen && (
            <motion.aside initial={{ x: -280, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: -280, opacity: 0 }} transition={{ type: "spring", duration: 0.35, bounce: 0.1 }}
              style={{ position: "absolute", inset: "0 auto 0 0", width: 280, zIndex: 5, background: "var(--sidebar)", borderRight: "1px solid var(--sidebar-border)", display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderBottom: "1px solid var(--sidebar-border)" }}>
                <span style={{ fontSize: 13, fontWeight: 650 }}>Chat history</span>
                <button onClick={() => setSidebarOpen(false)} style={{ background: "none", border: "none", color: "var(--muted-foreground)", cursor: "pointer", display: "grid", placeItems: "center" }}><X size={16} /></button>
              </div>
              <div style={{ padding: 10 }}>
                <button aria-label="New chat" title="New chat" onClick={startNewSession} style={{ ...iconBtn, width: "100%", height: 36, justifyContent: "center" }}><Plus size={14} /></button>
              </div>
              <div style={{ flex: 1, overflow: "auto", padding: "0 10px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
                {sessions.map((s: SessionMeta) => (
                  <div key={s.id} role="button" tabIndex={0} onClick={() => openSession(s.id)} onKeyDown={(event) => { if (event.key === "Enter") openSession(s.id); }}
                    style={{ textAlign: "left", padding: "10px", borderRadius: 8, background: s.id === sessionIdRef.current ? "var(--sidebar-accent)" : "color-mix(in srgb, var(--card) 45%, transparent)", border: "1px solid var(--sidebar-border)", cursor: "pointer", color: "var(--foreground)", boxShadow: s.id === sessionIdRef.current ? "inset 0 0 0 1px color-mix(in srgb, var(--foreground) 14%, transparent)" : "none" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                      <div style={{ fontSize: 12, fontWeight: 650, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.title || "New chat"}</div>
                      {s.id === sessionIdRef.current && <span style={{ width: 7, height: 7, borderRadius: 999, background: "#34d399", flex: "0 0 auto" }} />}
                    </div>
                    <div style={{ marginTop: 6, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, fontSize: 10, color: "var(--muted-foreground)" }}>
                      <span>{estimateSessionTokens(loadCachedMessages(s.id)) || s.tokenCount || 0} tokens</span>
                      <span>{new Date(s.updatedAt).toLocaleDateString()}</span>
                    </div>
                    <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
                      <button type="button" title="Rename chat" onClick={(event) => { event.stopPropagation(); renameSession(s); }} style={{ ...miniSessionBtn }}><Pencil size={12} /> Rename</button>
                      <button type="button" title="Delete chat" onClick={(event) => { event.stopPropagation(); removeSession(s); }} style={{ ...miniSessionBtn, color: "var(--destructive)" }}><Trash2 size={12} /> Delete</button>
                    </div>
                  </div>
                ))}
                {sessions.length === 0 && <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>No saved sessions yet.</span>}
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        <div className="marvex-chat-main">
          <BackgroundPlus plusColor="#fb3a5d" plusSize={60} fade={false} className="marvex-chat-bg pointer-events-none opacity-20" />
          <div className="marvex-chat-content">
            {activeTab === "chat" && (
              <MarvexChatShell
                assistantOrbState={orbState}
                messages={messages}
                micActive={dictationActive}
                composerValue={composerText}
                onComposerValueChange={setComposerText}
                onSubmit={(text) => { setComposerText(""); void send(text); }}
                onToggleVoice={toggleDictation}
                voiceSessionActive={voiceSessionActive}
                voiceSessionListening={voiceSessionListening}
                voiceSessionCue={voiceSessionCue}
                onToggleVoiceSession={toggleVoiceSession}
                onApprovalDecision={decideChatApproval}
                onClarificationAnswer={answerClarification}
                onDeleteMessage={deleteMessage}
                onEditUserMessage={editUserMessage}
                onRetryAssistantMessage={retryAssistantMessage}
                onStop={stopChatTurn}
                pending={pending}
                modelLabel={activeModelOption?.name ?? (providers ? "Select model" : "Connecting runtime")}
                models={modelOptions}
                onSelectModel={selectModel}
                contextInputTokens={providerUsage.inputTokens}
                outputTokens={providerUsage.outputTokens}
                totalTokens={providerUsage.totalTokens}
                reasoningTokens={providerUsage.reasoningTokens}
                contextWindow={activeModelOption?.contextWindow}
                cachedInputTokens={providerUsage.cachedInputTokens}
                reasoningEffort={activeModelOption?.reasoningEffort}
                reasoningEffortOptions={activeModelOption?.reasoningEffortOptions}
                onSelectReasoningEffort={selectReasoningEffort}
                renderAssistantOrb={(state) => <AgentOrb agentState={state ?? orbState} />}
              />
            )}

            {activeTab === "status" && (
              <div style={{ flex: 1, overflow: "auto", padding: 20 }}><StatusView backend={backend} /></div>
            )}
            {activeTab === "voice" && (
              <div style={{ flex: 1, overflow: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 24 }}>
                <VoiceMode
                />
              </div>
            )}
            {activeTab === "logs" && (
              <div style={{ flex: 1, overflow: "auto", padding: 20 }}><LogsView /></div>
            )}
            {activeTab === "memories" && (
              <div style={{ flex: 1, overflow: "auto", padding: 20 }}><MemorySettings /></div>
            )}
            {activeTab === "settings" && (
              <div style={{ flex: 1, overflow: "auto", padding: 20 }}><ControlPlaneSettings /></div>
            )}
          </div>
        </div>
      </div>

      <footer style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, padding: "8px 16px", borderTop: "1px solid var(--sidebar-border)", background: "var(--sidebar)" }}>
        <LimelightNav items={navItems} defaultActiveIndex={activeNavIndex} onTabChange={(idx) => navItems[idx]?.onClick()} />
        <div style={{ width: 1, height: 28, background: "var(--border)" }} />
        <button onClick={() => { persistMode("overlay"); void showOverlay(); }} title="Switch to Overlay (Marvex presence)" style={{ ...iconBtn, width: 44, height: 44, borderRadius: 12 }}><Radio size={18} /></button>
      </footer>
    </div>
  );
}


function approvalFromTurnResult(result: unknown, text: string): ChatApproval | undefined {
  if (!result || typeof result !== "object") return undefined;
  const metadata = (result as { metadata?: unknown }).metadata;
  const approval = metadata && typeof metadata === "object" ? (metadata as { approval_request?: unknown }).approval_request : undefined;
  if (!approval || typeof approval !== "object") return undefined;
  const request = approval as { approval_request_id?: unknown; trace_id?: unknown; turn_id?: unknown };
  if (typeof request.approval_request_id !== "string" || typeof request.trace_id !== "string" || typeof request.turn_id !== "string") return undefined;
  return {
    approvalId: request.approval_request_id,
    traceId: request.trace_id,
    turnId: request.turn_id,
    text,
    status: "pending",
  };
}

function clarificationFromTurnResult(result: unknown, originalText: string): MarvexChatClarification | undefined {
  if (!result || typeof result !== "object") return undefined;
  const metadata = (result as { metadata?: unknown }).metadata;
  const raw = metadata && typeof metadata === "object" ? (metadata as { clarification?: unknown }).clarification : undefined;
  if (!raw || typeof raw !== "object") return undefined;
  const obj = raw as { kind?: unknown; title?: unknown; options?: unknown };
  if (typeof obj.title !== "string") return undefined;
  const kind: MarvexChatClarification["kind"] = obj.kind === "multi" || obj.kind === "text" ? obj.kind : "single";
  const options = Array.isArray(obj.options)
    ? obj.options.flatMap((entry): MarvexChatClarification["options"] => {
        if (!entry || typeof entry !== "object") return [];
        const option = entry as { id?: unknown; label?: unknown; description?: unknown };
        if (typeof option.id !== "string" || typeof option.label !== "string") return [];
        return [{ id: option.id, label: option.label, description: typeof option.description === "string" ? option.description : undefined }];
      })
    : [];
  // Always allow a custom answer, regardless of the backend hint.
  return { kind, title: obj.title, allowCustom: true, options, originalText };
}

function AgentOrb({ agentState }: { agentState: AgentOrbState }) {
  return (
    <OrbBoundary>
      <Suspense fallback={<OrbFallback />}>
        <LazyOrb className="h-full w-full" agentState={agentState} />
      </Suspense>
    </OrbBoundary>
  );
}

class OrbBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return <OrbFallback />;
    return this.props.children;
  }
}

function OrbFallback() {
  return (
    <div
      aria-label="Marvex orb fallback"
      className="h-full w-full"
      style={{
        background: "radial-gradient(circle at 35% 30%, #ffffff 0%, #cadcfc 28%, #a0b9d1 62%, rgba(15,23,42,0.15) 100%)",
      }}
    />
  );
}

const iconBtn: React.CSSProperties = {
  display: "grid",
  placeItems: "center",
  width: 34,
  height: 34,
  borderRadius: 8,
  border: "1px solid var(--border)",
  background: "var(--secondary)",
  color: "var(--foreground)",
  cursor: "pointer",
};

const miniSessionBtn: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  border: "1px solid var(--border)",
  borderRadius: 6,
  background: "var(--secondary)",
  color: "var(--muted-foreground)",
  padding: "4px 6px",
  fontSize: 10,
  cursor: "pointer",
};

function WakewordBadge({ state }: { state: WakewordState }) {
  const awake = state === "running" || state === "enabled";
  const label = awake ? "Wake word • Awake" : "Wake word • Dormant";
  const color = awake ? "#34d399" : "#9ca3af";
  return (
    <span title="Wake word engine status" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, padding: "4px 9px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--foreground)" }}>
      <Ear size={12} style={{ color }} />
      {label}
    </span>
  );
}
