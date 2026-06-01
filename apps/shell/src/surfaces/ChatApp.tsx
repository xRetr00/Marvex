import { Component, lazy, Suspense, useEffect, useMemo, useRef, useState, useCallback, type ReactNode } from "react";
import { MessageSquare, Settings, Radio, History, X, Plus, Activity, ScrollText, Power, RotateCcw, Ear, Volume2, Pencil, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { listen } from "@/lib/tauriBridge";
import { type CitationRef, type TurnStage, type UiDirective } from "@/lib/localTurn";
import { cancelActiveChatTurn, deleteChatSession, getShellRuntimeConfig, renameChatSession, showOverlay, submitChatTurnStream, resumeApprovalTurn, startBackend, marvexShutdown, marvexRestart, createChatSession, listChatSessions, type BackendSession, type ShellRuntimeConfig } from "@/lib/shellCommands";
import { persistMode } from "@/lib/modeStore";
import { displayDetail, idleAssistantState, normalizeAssistantState, type AssistantStateEvent, type AssistantStatusKind } from "@/lib/assistantState";
import { outcomeFromTurnResult, outcomeFromError } from "@/lib/turnOutcome";
import { providerResponseIdFromTurnResult } from "@/lib/turnResultHelpers";
import { deleteCachedSession, estimateSessionTokens, loadCachedMessages, renameCachedSession, saveCachedMessages, rememberSession, listCachedSessions, type SessionMeta, type StoredMessage } from "@/lib/sessionStore";
import { fetchProviders, selectProviderModel, type ProviderCatalog } from "@/lib/providerControlClient";
import { useBackendStatus, type WakewordState } from "@/lib/backendStatus";
import { startVoiceWorker, stopVoiceWorker, fetchVoiceWorkerStatus, speakVoiceWorker, listenVoiceWorker, transcriptFromStatus } from "@/lib/voiceControlClient";

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

type ChatApproval = { approvalId: string; traceId: string; turnId: string; text: string; status: "pending" | "approved" | "denied" | "cancelled" };
type ChatMessage = { role: "user" | "assistant" | "system"; text: string; stages?: TurnStage[]; citations?: CitationRef[]; directives?: UiDirective[]; approval?: ChatApproval; clarification?: MarvexChatClarification; streaming?: boolean };
type TabId = "chat" | "voice" | "status" | "logs" | "settings";
type AgentOrbState = "thinking" | "listening" | "talking" | null;

const LazyOrb = lazy(() => import("@/components/chat-messages-for-ui/agent-simple-orb").then((module) => ({ default: module.Orb })));

function agentStateFromStatus(status: AssistantStatusKind): AgentOrbState {
  if (status === "listening") return "listening";
  if (status === "talking") return "talking";
  if (status === "thinking" || status === "working" || status === "using_tools" || status === "mcp" || status === "skills" || status === "searching_web") return "thinking";
  return null;
}

export function ChatApp() {
  const [config, setConfig] = useState<ShellRuntimeConfig | null>(null);
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const sessionIdRef = useRef<string | null>(null);
  const previousResponseIdsRef = useRef<Record<string, string>>({});
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "system", text: "Marvex is ready." }]);
  const [sessions, setSessions] = useState<SessionMeta[]>(() => listCachedSessions());
  const [providers, setProviders] = useState<ProviderCatalog | null>(null);
  const [pending, setPending] = useState(false);
  const [micActive, setMicActive] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("chat");

  const backend = useBackendStatus();
  const [helloDone, setHelloDone] = useState(false);
  const [booted, setBooted] = useState(false);

  const activateBackendSession = useCallback((session: BackendSession) => {
    const id = session.session_ref.ref_id;
    sessionIdRef.current = id;
    const cached = listCachedSessions().find((item) => item.id === id);
    if (cached?.lastProviderResponseId) previousResponseIdsRef.current[id] = cached.lastProviderResponseId;
    rememberSession({ id, title: session.title, updatedAt: session.updated_at_unix_ms });
    const restored = loadCachedMessages(id) as ChatMessage[];
    setMessages(restored.length ? restored : [{ role: "system", text: "Marvex is ready." }]);
    setSessions(listCachedSessions());
  }, []);

  useEffect(() => {
    void getShellRuntimeConfig().then(setConfig).catch(() => setConfig(null));
    void fetchProviders().then(setProviders).catch(() => undefined);
    let cleanup: VoidFunction | undefined;
    void listen("assistant-state", (event) => {
      try { setState(normalizeAssistantState(event.payload)); }
      catch { setState(idleAssistantState); }
    }).then((unlisten) => { cleanup = unlisten; });
    return () => cleanup?.();
  }, []);

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
          next[i] = patch;
          return next;
        }
      }
      next.push(patch);
      return next;
    });
  }, []);

  const send = useCallback(async (text: string, options: { appendUser?: boolean } = {}): Promise<string> => {
    if (!text.trim() || pending) return "";
    const appendUser = options.appendUser ?? true;
    setPending(true);
    // Append a user message only for direct user turns. Follow-up UI controls
    // such as clarification answers and approvals update the active assistant
    // turn instead of creating transcript noise.
    if (appendUser) {
      setMessages((prev) => [...prev, { role: "user", text }, { role: "assistant", text: "", streaming: true }]);
    } else {
      updateLastAssistant({ role: "assistant", text: "", streaming: true });
    }
    let replyText = "";
    let streamed = "";
    try {
      const sessionId = sessionIdRef.current;
      if (!sessionId) throw new Error("backend session unavailable");
      const result = await submitChatTurnStream(
        text,
        { session_id: sessionId },
        previousResponseIdsRef.current[sessionId],
        (chunk) => {
          streamed += chunk;
          updateLastAssistant({ role: "assistant", text: streamed, streaming: true });
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
      replyText = outcome.text;
      // Reconcile with the authoritative final result (text + stages + refs).
      updateLastAssistant({ role: "assistant", text: outcome.text, stages: outcome.stages, citations: outcome.citations, directives: outcome.directives, approval: approvalFromTurnResult(result, text), clarification: clarificationFromTurnResult(result, text) });
    } catch (error) {
      const outcome = outcomeFromError(error);
      replyText = outcome.text;
      updateLastAssistant({ role: "assistant", text: outcome.text });
    } finally {
      setPending(false);
    }
    return replyText;
  }, [pending, updateLastAssistant]);

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
    void cancelActiveChatTurn().catch(() => undefined);
    setPending(false);
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
    }
  }, []);

  const toggleVoiceCapture = useCallback(() => {
    const next = !micActive;
    setMicActive(next);
    void (next ? startVoiceWorker() : stopVoiceWorker()).catch(() => setMicActive(!next));
  }, [micActive]);

  // Voice loop bridge (docs/TODO/04): poll the worker for a freshly recognized
  // transcript, run it as a chat turn, and speak the reply back through the
  // worker. The worker handles wake -> capture -> STT and emits transcript_text;
  // the shell mediates turn + speak because the worker is loopback-isolated from
  // Core. This must run for HANDS-FREE wake word too (not only the manual mic
  // button): the wake word fires in the worker independently, so if we only
  // polled while micActive, "Hey Marvex" would transcribe but nothing would
  // reach the UI.
  const wakewordActive = backend?.wakeword === "enabled" || backend?.wakeword === "running";
  const voiceBridgeActive = micActive || wakewordActive;
  const lastVoiceEventRef = useRef<string>("");
  useEffect(() => {
    if (!voiceBridgeActive) return;
    let cancelled = false;
    let busy = false;
    const timer = setInterval(() => {
      if (busy) return;
      busy = true;
      void fetchVoiceWorkerStatus()
        .then(async (status) => {
          if (cancelled) return;
          const transcript = transcriptFromStatus(status);
          if (!transcript || transcript.eventId === lastVoiceEventRef.current) return;
          lastVoiceEventRef.current = transcript.eventId;
          const reply = await send(transcript.text);
          if (reply.trim()) {
            await speakVoiceWorker(reply, { bargeIn: true }).catch(() => undefined);
            // Hands-free multi-turn: after speaking, capture a follow-up without
            // requiring another wake word. If the user stays silent the worker
            // bails and we fall back to wake-word listening on the next poll.
            await listenVoiceWorker().catch(() => undefined);
          }
        })
        .catch(() => undefined)
        .finally(() => {
          busy = false;
        });
    }, 1500);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [voiceBridgeActive, send]);

  const navItems = useMemo(() => [
    { id: "chat" as TabId, icon: <MessageSquare />, label: "Chat", onClick: () => setActiveTab("chat") },
    { id: "voice" as TabId, icon: <Volume2 />, label: "Voice Mode", onClick: () => setActiveTab("voice") },
    { id: "status" as TabId, icon: <Activity />, label: "Status", onClick: () => setActiveTab("status") },
    { id: "logs" as TabId, icon: <ScrollText />, label: "Logs", onClick: () => setActiveTab("logs") },
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
    return rows.flatMap((provider) => (provider.models ?? []).map((model) => ({
      id: `${provider.provider_id}:${model}`,
      name: model,
      provider: provider.provider_id.split("_")[0],
      active: provider.provider_id === providers?.active_provider_id && model === provider.active_model,
      providerId: provider.provider_id,
      model,
    })));
  }, [providers]);

  const selectModel = useCallback((value: string) => {
    const found = modelOptions.find((model) => model.id === value);
    if (!found) return;
    void selectProviderModel(found.providerId, found.model).then(setProviders).catch(() => undefined);
  }, [modelOptions]);

  const openSession = useCallback((id: string) => {
    sessionIdRef.current = id;
    const cached = listCachedSessions().find((item) => item.id === id);
    if (cached?.lastProviderResponseId) {
      previousResponseIdsRef.current[id] = cached.lastProviderResponseId;
    } else {
      delete previousResponseIdsRef.current[id];
    }
    const restored = loadCachedMessages(id) as ChatMessage[];
    setMessages(restored.length ? restored : [{ role: "system", text: "Marvex is ready." }]);
    setSidebarOpen(false);
    setActiveTab("chat");
  }, []);

  const orbState = agentStateFromStatus(state.status);

  if (!booted) {
    return <StartupScreen backend={backend} onHelloDone={() => setHelloDone(true)} onRetry={() => void startBackend().catch(() => undefined)} />;
  }

  const TAB_TITLES: Record<TabId, string> = { chat: "Assistant Chat", voice: "Voice Mode", status: "Status", logs: "Logs / Traces / Telemetry", settings: "Settings" };
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
            <ScrambleText as="h1" text={TAB_TITLES[activeTab]} className="m-0 text-[17px] font-bold" style={{ color: "var(--foreground)" }} />
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
                micActive={micActive}
                onSubmit={(text) => { void send(text); }}
                onToggleVoice={toggleVoiceCapture}
                onApprovalDecision={decideChatApproval}
                onClarificationAnswer={answerClarification}
                onStop={stopChatTurn}
                pending={pending}
                activityLabel={state.status === "idle" ? "Marvex is thinking" : displayDetail(state)}
                modelLabel={modelOptions.find((model) => model.active)?.name ?? (config ? "Select model" : "Connecting runtime")}
                models={modelOptions}
                onSelectModel={selectModel}
                renderAssistantOrb={(state) => <AgentOrb agentState={state ?? orbState} />}
              />
            )}

            {activeTab === "status" && (
              <div style={{ flex: 1, overflow: "auto", padding: 20 }}><StatusView backend={backend} /></div>
            )}
            {activeTab === "voice" && (
              <div style={{ flex: 1, overflow: "auto", padding: 20 }}><VoiceMode /></div>
            )}
            {activeTab === "logs" && (
              <div style={{ flex: 1, overflow: "auto", padding: 20 }}><LogsView /></div>
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
  const map: Record<WakewordState, { label: string; color: string }> = {
    running: { label: "Hey Marvex • on", color: "#34d399" },
    enabled: { label: "Hey Marvex • on", color: "#34d399" },
    not_ready: { label: "Wake word • setup", color: "#f59e0b" },
    disabled: { label: "Wake word • off", color: "#9ca3af" },
    unknown: { label: "Wake word • …", color: "#9ca3af" },
  };
  const { label, color } = map[state];
  return (
    <span title="Wake word engine status" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, padding: "4px 9px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--foreground)" }}>
      <Ear size={12} style={{ color }} />
      {label}
    </span>
  );
}
