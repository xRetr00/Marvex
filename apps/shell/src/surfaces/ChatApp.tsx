import { Component, lazy, Suspense, useEffect, useMemo, useRef, useState, useCallback, type ReactNode } from "react";
import { MessageSquare, Settings, Radio, History, X, Plus, Activity, ScrollText, Power, RotateCcw, Volume2, AlertTriangle, Cpu, Sparkles, Bot, Zap, Globe, ChevronDown, MessageSquareDot } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { listen } from "@/lib/tauriBridge";
import { type TurnStage, type UiDirective } from "@/lib/localTurn";
import { getShellRuntimeConfig, showOverlay, submitChatTurn, resumeApprovalTurn, startBackend, marvexShutdown, marvexRestart, createChatSession, listChatSessions, type BackendSession, type ShellRuntimeConfig } from "@/lib/shellCommands";
import { persistMode } from "@/lib/modeStore";
import { idleAssistantState, normalizeAssistantState, statusLabel, type AssistantStateEvent, type AssistantStatusKind } from "@/lib/assistantState";
import { outcomeFromTurnResult, outcomeFromError } from "@/lib/turnOutcome";
import { providerResponseIdFromTurnResult } from "@/lib/turnResultHelpers";
import { loadCachedMessages, saveCachedMessages, rememberSession, listCachedSessions, type SessionMeta, type StoredMessage } from "@/lib/sessionStore";
import { useBackendStatus, type WakewordState } from "@/lib/backendStatus";
import { startVoiceWorker, stopVoiceWorker } from "@/lib/voiceControlClient";

import { LimelightNav } from "@/components/dock";
import { Loader } from "@/components/loader";
import { ScrambleText } from "@/components/scramble-text";
import { MarvexChatShell } from "@/components/chatbot-main/MarvexChatShell";
import { Status, StatusIndicator, StatusLabel } from "@/components/status-for-ui/status";
import { StartupScreen } from "@/components/marvex/StartupScreen";
import { StatusView } from "@/components/marvex/StatusView";
import { LogsView } from "@/components/marvex/LogsView";
import { VoiceMode } from "./VoiceMode";
import { ControlPlaneSettings } from "./ControlPlaneSettings";

type ChatApproval = { approvalId: string; traceId: string; turnId: string; text: string; status: "pending" | "approved" | "denied" | "cancelled" };
type ChatMessage = { role: "user" | "assistant" | "system"; text: string; stages?: TurnStage[]; directives?: UiDirective[]; approval?: ChatApproval };
type TabId = "chat" | "voice" | "status" | "logs" | "settings";
type AgentOrbState = "thinking" | "listening" | "talking" | null;

const LazyOrb = lazy(() => import("@/components/chat-messages-for-ui/agent-simple-orb").then((module) => ({ default: module.Orb })));

// Fix #8: include needs_approval so orb signals blocked state
function agentStateFromStatus(status: AssistantStatusKind): AgentOrbState {
  if (status === "listening") return "listening";
  if (status === "talking") return "talking";
  if (status === "thinking" || status === "working" || status === "using_tools" || status === "mcp" || status === "skills" || status === "searching_web" || status === "needs_approval" || status === "asking") return "thinking";
  return null;
}

export function ChatApp() {
  const [config, setConfig] = useState<ShellRuntimeConfig | null>(null);
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const sessionIdRef = useRef<string | null>(null);
  const previousResponseIdsRef = useRef<Record<string, string>>({});
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "system", text: "Marvex is ready." }]);
  const [sessions, setSessions] = useState<SessionMeta[]>(() => listCachedSessions());
  const [pending, setPending] = useState(false);
  const [micActive, setMicActive] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Fix #9: default to undefined; derive activeNavIndex safely without defaulting to 0
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
    // Fix #11: reset assistant state to idle when switching sessions
    setState(idleAssistantState);
    setSessions(listCachedSessions());
  }, []);

  useEffect(() => {
    void getShellRuntimeConfig().then(setConfig).catch(() => setConfig(null));
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

  const send = useCallback(async (text: string) => {
    if (!text.trim() || pending) return;
    setPending(true);
    setMessages((prev) => [...prev, { role: "user", text }]);
    try {
      const sessionId = sessionIdRef.current;
      if (!sessionId) throw new Error("backend session unavailable");
      const result = await submitChatTurn(text, { session_id: sessionId }, previousResponseIdsRef.current[sessionId]);
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
      const approval = approvalFromTurnResult(result, text);
      setMessages((prev) => [...prev, { role: "assistant", text: outcome.text, stages: outcome.stages, directives: outcome.directives, approval }]);
    } catch (error) {
      const outcome = outcomeFromError(error);
      setMessages((prev) => [...prev, { role: "assistant", text: outcome.text }]);
    } finally {
      setPending(false);
    }
  }, [pending]);

  // Fix #6: approval outcome goes as a separate follow-up message, not
  // concatenated into the original request bubble with \n\n.
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
      // Mark the original approval message as resolved
      setMessages((prev) => [
        ...prev.map((message) => {
          if (message.approval?.approvalId !== approval.approvalId) return message;
          return {
            ...message,
            approval: {
              ...message.approval,
              status: decision === "approve" ? "approved" : decision === "cancel" ? "cancelled" : "denied",
            } as ChatApproval,
          };
        }),
        // Append the outcome as a new assistant message so RichMessage parses it cleanly
        { role: "assistant" as const, text: outcome.text, stages: outcome.stages, directives: outcome.directives },
      ]);
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

  const navItems = useMemo(() => [
    { id: "chat" as TabId, icon: <MessageSquare />, label: "Chat", onClick: () => setActiveTab("chat") },
    { id: "voice" as TabId, icon: <Volume2 />, label: "Voice Mode", onClick: () => setActiveTab("voice") },
    { id: "status" as TabId, icon: <Activity />, label: "Status", onClick: () => setActiveTab("status") },
    { id: "logs" as TabId, icon: <ScrollText />, label: "Logs", onClick: () => setActiveTab("logs") },
    { id: "settings" as TabId, icon: <Settings />, label: "Settings", onClick: () => setActiveTab("settings") },
  ], []);

  // Fix #9: never silently fall back to index 0; use the actual found index
  // only, which LimelightNav can default-handle if it receives -1.
  const activeNavIndex = navItems.findIndex((n) => n.id === activeTab);

  const startNewSession = useCallback(() => {
    void createChatSession("New chat").then(({ session }) => {
      activateBackendSession(session);
      delete previousResponseIdsRef.current[session.session_ref.ref_id];
      setMessages([{ role: "system", text: "New chat started." }]);
      setSidebarOpen(false);
      setActiveTab("chat");
    }).catch(() => undefined);
  }, [activateBackendSession]);

  // Fix #11: openSession also resets assistant state
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
    setState(idleAssistantState);
    setSidebarOpen(false);
    setActiveTab("chat");
  }, []);

  const orbState = agentStateFromStatus(state.status);

  if (!booted) {
    return <StartupScreen backend={backend} onHelloDone={() => setHelloDone(true)} onRetry={() => void startBackend().catch(() => undefined)} />;
  }

  const TAB_TITLES: Record<TabId, string> = { chat: "Assistant Chat", voice: "Voice Mode", status: "Status", logs: "Logs / Traces / Telemetry", settings: "Settings" };

  return (
    <div className="marvex-chat-shell flex flex-col h-screen min-h-0 relative z-[1]">
      <header className="marvex-chat-header">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => setSidebarOpen((v) => !v)} title="Sessions" style={iconBtn}><History size={16} /></button>
          <img src="/assets/Marvex_App_192.png" alt="Marvex" style={{ width: 30, height: 30, borderRadius: 8, objectFit: "contain" }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          <div>
            <ScrambleText as="h1" text={TAB_TITLES[activeTab]} className="m-0 text-[17px] font-bold" style={{ color: "var(--foreground)" }} />
            {/* Connection status dot — replaces the raw localhost URL */}
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 2 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: config ? "#34d399" : "#f59e0b", flexShrink: 0, display: "block" }} />
              <span style={{ fontSize: 10, color: "var(--muted-foreground)", fontWeight: 500 }}>
                {config ? "Connected" : "Connecting..."}
              </span>
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <WakewordBadge state={backend?.wakeword ?? "unknown"} />
          {/* Fix #8: show a distinct blocked badge when needs_approval */}
          {state.status === "needs_approval" && (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, padding: "3px 9px", borderRadius: 999, border: "1px solid var(--destructive)", background: "color-mix(in srgb, var(--destructive) 12%, transparent)", color: "var(--destructive)" }}>
              <AlertTriangle size={11} />
              Needs Approval
            </span>
          )}
          {(pending || state.status !== "idle") && <Loader variant="circular" size="sm" />}
          <Status status={state.status === "idle" ? "online" : "degraded"}>
            <StatusIndicator />
            <StatusLabel>{state.status === "idle" ? "Ready" : statusLabel(state.status)}</StatusLabel>
          </Status>
          <div style={{ width: 1, height: 24, background: "var(--border)" }} />
          <button onClick={() => void marvexRestart()} title="Restart Marvex" style={iconBtn}><RotateCcw size={15} /></button>
          <button onClick={() => void marvexShutdown()} title="Shutdown Marvex" style={{ ...iconBtn, color: "var(--destructive)" }}><Power size={15} /></button>
        </div>
      </header>

      <div style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", position: "relative", background: "var(--sidebar)" }}>
        <AnimatePresence>
          {sidebarOpen && (
            <motion.aside
              initial={{ x: -288, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: -288, opacity: 0 }}
              transition={{ type: "spring", duration: 0.32, bounce: 0.08 }}
              className="marvex-sidebar"
            >
              {/* Header */}
              <div className="marvex-sidebar-header">
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <MessageSquareDot size={15} style={{ color: "var(--muted-foreground)" }} />
                  <span style={{ fontSize: 13, fontWeight: 650, letterSpacing: "-0.01em" }}>Chats</span>
                </div>
                <button onClick={() => setSidebarOpen(false)} className="marvex-sidebar-close" aria-label="Close sidebar"><X size={15} /></button>
              </div>

              {/* New chat button */}
              <div style={{ padding: "10px 12px 6px" }}>
                <button onClick={startNewSession} className="marvex-new-chat-btn">
                  <Plus size={14} />
                  New chat
                </button>
              </div>

              {/* Session list */}
              <div style={{ flex: 1, overflow: "auto", padding: "4px 8px 12px", display: "flex", flexDirection: "column", gap: 2 }}>
                {sessions.length === 0 && (
                  <div className="marvex-sidebar-empty">
                    <MessageSquare size={28} style={{ color: "var(--muted-foreground)", opacity: 0.4 }} />
                    <span style={{ fontSize: 12, color: "var(--muted-foreground)", textAlign: "center", lineHeight: 1.5 }}>No saved chats yet.<br />Start a new one above.</span>
                  </div>
                )}
                {sessions.map((s: SessionMeta) => {
                  const isActive = s.id === sessionIdRef.current;
                  const relTime = relativeTime(s.updatedAt);
                  return (
                    <button key={s.id} onClick={() => openSession(s.id)} className={`marvex-sidebar-item${isActive ? " is-active" : ""}`}>
                      <div className="marvex-sidebar-item-accent" />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div className="marvex-sidebar-item-title">{s.title || "New chat"}</div>
                        <div className="marvex-sidebar-item-meta">
                          <span>{relTime}</span>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        <div className="marvex-chat-main">
          {/* Fix #12: fade={true} prevents + pattern from clipping at border-radius */}
          <div className="marvex-chat-bg pointer-events-none absolute inset-0 z-0 overflow-hidden rounded-tl-xl opacity-[0.15]"
            style={{ background: "radial-gradient(ellipse 80% 60% at 50% 0%, color-mix(in srgb, #fb3a5d 40%, transparent), transparent)" }} />
          <div className="marvex-chat-content">
            {activeTab === "chat" && config && (
              <div className="marvex-chat-model-bar">
                <MiniModelPill config={config} />
              </div>
            )}
            {activeTab === "chat" && (
              <MarvexChatShell
                assistantOrbState={orbState}
                messages={messages}
                micActive={micActive}
                onSubmit={send}
                onToggleVoice={toggleVoiceCapture}
                onApprovalDecision={decideChatApproval}
                pending={pending}
                agentStatus={state.status}
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

// Fix #5: also check flat approval_request_id directly on metadata
function approvalFromTurnResult(result: unknown, text: string): ChatApproval | undefined {
  if (!result || typeof result !== "object") return undefined;
  const metadata = (result as { metadata?: unknown }).metadata;
  if (!metadata || typeof metadata !== "object") return undefined;
  const meta = metadata as Record<string, unknown>;

  // Nested shape: metadata.approval_request.approval_request_id
  const nested = meta.approval_request;
  const request = (nested && typeof nested === "object" ? nested : meta) as Record<string, unknown>;

  if (typeof request.approval_request_id !== "string" || typeof request.trace_id !== "string" || typeof request.turn_id !== "string") return undefined;
  return {
    approvalId: request.approval_request_id,
    traceId: request.trace_id,
    turnId: request.turn_id,
    text,
    status: "pending",
  };
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
  static getDerivedStateFromError() { return { failed: true }; }
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
      style={{ background: "radial-gradient(circle at 35% 30%, #ffffff 0%, #cadcfc 28%, #a0b9d1 62%, rgba(15,23,42,0.15) 100%)" }}
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

// ---- Provider icon map ----
function providerIcon(providerId: string): ReactNode {
  const id = (providerId ?? "").toLowerCase();
  if (id.includes("openai") || id.includes("gpt")) return <Sparkles size={12} />;
  if (id.includes("anthropic") || id.includes("claude")) return <Zap size={12} />;
  if (id.includes("lm") || id.includes("lmstudio") || id.includes("litellm") || id.includes("local")) return <Cpu size={12} />;
  if (id.includes("google") || id.includes("gemini")) return <Globe size={12} />;
  return <Bot size={12} />;
}

// ---- Mini model pill shown in the chat tab header bar ----
function MiniModelPill({ config }: { config: ShellRuntimeConfig }) {
  const providerId = (config as unknown as Record<string, string>).active_provider_id ?? "";
  const modelId = (config as unknown as Record<string, string>).active_model ?? "";
  const label = modelId || providerId || "Model";
  return (
    <div className="marvex-model-pill" title={`${providerId} / ${modelId}`}>
      <span className="marvex-provider-icon">{providerIcon(providerId)}</span>
      <span className="marvex-model-pill-label">{label.length > 28 ? label.slice(0, 26) + "…" : label}</span>
      <ChevronDown size={10} style={{ opacity: 0.5, flexShrink: 0 }} />
    </div>
  );
}

// ---- Relative time helper ----
function relativeTime(ms: number): string {
  const diff = Date.now() - ms;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

function WakewordBadge({ state }: { state: WakewordState }) {
  const map: Record<WakewordState, { label: string; color: string }> = {
    running: { label: "Hey Marvex", color: "#34d399" },
    enabled: { label: "Hey Marvex", color: "#34d399" },
    not_ready: { label: "Wake word setup", color: "#f59e0b" },
    disabled: { label: "Wake word off", color: "#9ca3af" },
    unknown: { label: "Wake word ...", color: "#9ca3af" },
  };
  const { label, color } = map[state];
  return (
    <span title="Wake word engine status" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, padding: "4px 9px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--foreground)" }}>
      <Ear size={12} style={{ color }} />
      {label}
    </span>
  );
}
