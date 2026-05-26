import { Component, lazy, Suspense, useEffect, useMemo, useRef, useState, useCallback, type ReactNode } from "react";
import { MessageSquare, Settings, Mic, MicOff, Radio, History, X, Plus, Activity, ScrollText, Power, RotateCcw, Ear, Volume2 } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { listen } from "@/lib/tauriBridge";
import { type TurnStage, type UiDirective } from "@/lib/localTurn";
import { getShellRuntimeConfig, showOverlay, submitChatTurn, startBackend, marvexShutdown, marvexRestart, createChatSession, listChatSessions, type BackendSession, type ShellRuntimeConfig } from "@/lib/shellCommands";
import { persistMode } from "@/lib/modeStore";
import { idleAssistantState, normalizeAssistantState, statusLabel, type AssistantStateEvent, type AssistantStatusKind } from "@/lib/assistantState";
import { outcomeFromTurnResult, outcomeFromError } from "@/lib/turnOutcome";
import { loadCachedMessages, saveCachedMessages, rememberSession, listCachedSessions, type SessionMeta, type StoredMessage } from "@/lib/sessionStore";
import { useBackendStatus, type WakewordState } from "@/lib/backendStatus";
import { startVoiceWorker, stopVoiceWorker } from "@/lib/voiceControlClient";

import { LimelightNav } from "@/components/dock";
import { Loader } from "@/components/loader";
import { Typewriter } from "@/components/typewriter";
import { ScrambleText } from "@/components/scramble-text";
import ChatInput from "@/components/prompt-input-dynamic-grow";
import { Message, MessageContent } from "@/components/ui/message";
import { RichMessage } from "@/components/marvex/RichMessage";
import { Status, StatusIndicator, StatusLabel } from "@/components/status-for-ui/status";
import { StartupScreen } from "@/components/marvex/StartupScreen";
import { StatusView } from "@/components/marvex/StatusView";
import { LogsView } from "@/components/marvex/LogsView";
import { VoiceMode } from "./VoiceMode";
import { ControlPlaneSettings } from "./ControlPlaneSettings";

type ChatMessage = { role: "user" | "assistant" | "system"; text: string; stages?: TurnStage[]; directives?: UiDirective[] };
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
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "system", text: "Marvex is ready. How can I help?" }]);
  const [sessions, setSessions] = useState<SessionMeta[]>(() => listCachedSessions());
  const [pending, setPending] = useState(false);
  const [micActive, setMicActive] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("chat");

  const backend = useBackendStatus();
  const [helloDone, setHelloDone] = useState(false);
  const [booted, setBooted] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const activateBackendSession = useCallback((session: BackendSession) => {
    const id = session.session_ref.ref_id;
    sessionIdRef.current = id;
    rememberSession({ id, title: session.title, updatedAt: session.updated_at_unix_ms });
    const restored = loadCachedMessages(id) as ChatMessage[];
    setMessages(restored.length ? restored : [{ role: "system", text: "Marvex is ready. How can I help?" }]);
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

  // Reveal chat once backend is ready AND the hello has played (hello always
  // plays on open).
  useEffect(() => {
    if (backend?.ready && helloDone && !booted) {
      const t = setTimeout(() => setBooted(true), 350);
      return () => clearTimeout(t);
    }
  }, [backend?.ready, helloDone, booted]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

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
      const result = await submitChatTurn(text, { session_id: sessionId });
      const outcome = outcomeFromTurnResult(result);
      setMessages((prev) => [...prev, { role: "assistant", text: outcome.text, stages: outcome.stages, directives: outcome.directives }]);
    } catch (error) {
      const outcome = outcomeFromError(error);
      setMessages((prev) => [...prev, { role: "assistant", text: outcome.text }]);
    } finally {
      setPending(false);
    }
  }, [pending]);

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
  const activeNavIndex = Math.max(0, navItems.findIndex((n) => n.id === activeTab));

  const startNewSession = useCallback(() => {
    void createChatSession("New chat").then(({ session }) => {
      activateBackendSession(session);
      setMessages([{ role: "system", text: "New chat started." }]);
      setSidebarOpen(false);
      setActiveTab("chat");
    }).catch(() => undefined);
  }, []);

  const openSession = useCallback((id: string) => {
    sessionIdRef.current = id;
    const restored = loadCachedMessages(id) as ChatMessage[];
    setMessages(restored.length ? restored : [{ role: "system", text: "Marvex is ready. How can I help?" }]);
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
            <p style={{ margin: "1px 0 0", color: "var(--muted-foreground)", fontSize: 11 }}>{config ? `${config.core_base_url}` : "Connecting..."}</p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <WakewordBadge state={backend?.wakeword ?? "unknown"} />
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

      <div style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", position: "relative", background: "var(--sidebar)", padding: "0 0 0 0" }}>
        <AnimatePresence>
          {sidebarOpen && (
            <motion.aside initial={{ x: -280, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: -280, opacity: 0 }} transition={{ type: "spring", duration: 0.35, bounce: 0.1 }}
              style={{ position: "absolute", inset: "0 auto 0 0", width: 280, zIndex: 5, background: "var(--sidebar)", borderRight: "1px solid var(--sidebar-border)", display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderBottom: "1px solid var(--sidebar-border)" }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Sessions</span>
                <button onClick={() => setSidebarOpen(false)} style={{ background: "none", border: "none", color: "var(--muted-foreground)", cursor: "pointer", display: "grid", placeItems: "center" }}><X size={16} /></button>
              </div>
              <div style={{ padding: 10 }}>
                <button onClick={startNewSession} style={{ ...iconBtn, width: "100%", height: 36, gap: 6 }}><Plus size={14} /> New chat</button>
              </div>
              <div style={{ flex: 1, overflow: "auto", padding: "0 10px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
                {sessions.map((s: SessionMeta) => (
                  <button key={s.id} onClick={() => openSession(s.id)}
                    style={{ textAlign: "left", padding: "8px 10px", borderRadius: 8, background: s.id === sessionIdRef.current ? "var(--sidebar-accent)" : "transparent", border: "1px solid var(--sidebar-border)", cursor: "pointer", color: "var(--foreground)" }}>
                    <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.title || "New chat"}</div>
                    <div style={{ fontSize: 10, color: "var(--muted-foreground)" }}>{new Date(s.updatedAt).toLocaleString()}</div>
                  </button>
                ))}
                {sessions.length === 0 && <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>No saved sessions yet.</span>}
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        <div className="marvex-chat-main">
          {activeTab === "chat" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
              <div className="marvex-chat-scroll">
                <div className="marvex-chat-thread">
                  {messages.map((msg, idx) => (
                    <Message key={`${msg.role}-${idx}`} from={msg.role === "user" ? "user" : "assistant"} className="py-0">
                      {msg.role === "assistant" ? (
                        <MessageContent variant="flat" className="w-full max-w-[min(100%,72ch)] text-[13px] leading-[1.65]"><RichMessage text={msg.text} stages={msg.stages} directives={msg.directives} /></MessageContent>
                      ) : (
                        <MessageContent
                          variant={msg.role === "system" ? "flat" : "contained"}
                          className={msg.role === "system" ? "text-[13px] text-muted-foreground" : "w-fit max-w-[min(80%,56ch)] overflow-hidden break-words rounded-2xl rounded-br-lg border border-border/30 bg-gradient-to-br from-secondary to-muted px-3.5 py-2 text-[13px] leading-[1.65] shadow-[var(--shadow-card)]"}
                        >
                          {msg.text}
                        </MessageContent>
                      )}
                      {msg.role === "assistant" && (
                        <div className="marvex-message-orb"><AgentOrb agentState={orbState} /></div>
                      )}
                    </Message>
                  ))}
                  {pending && (
                    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "2px 0" }}>
                      <div className="marvex-message-orb"><AgentOrb agentState="thinking" /></div>
                      <Loader variant="loading-dots" text="Marvex is thinking" />
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              </div>
              {!pending && messages.length <= 1 && (
                <div style={{ width: "min(100%, 896px)", margin: "0 auto", padding: "0 16px 6px", textAlign: "center" }}>
                  <Typewriter text={["How can I help you today?", "Search the web, write a file, plan a task...", "Ask me anything."]} speed={55} deleteSpeed={25} waitTime={2200} loop className="text-sm" />
                </div>
              )}
              <div className="marvex-composer-bar">
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <button title="Microphone" onClick={toggleVoiceCapture} style={{ ...iconBtn, width: 36, height: 36, borderRadius: 8, background: micActive ? "var(--primary)" : "transparent", color: micActive ? "var(--primary-foreground)" : "var(--muted-foreground)" }}>
                    {micActive ? <MicOff size={16} /> : <Mic size={16} />}
                  </button>
                  <div style={{ flex: 1 }}>
                    <ChatInput placeholder="Ask anything..." disabled={pending} onSubmit={send} textColor="var(--foreground)" backgroundOpacity={0.06} />
                  </div>
                </div>
              </div>
            </div>
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

      <footer style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, padding: "8px 16px", borderTop: "1px solid var(--sidebar-border)", background: "var(--sidebar)" }}>
        <LimelightNav items={navItems} defaultActiveIndex={activeNavIndex} onTabChange={(idx) => navItems[idx]?.onClick()} />
        <div style={{ width: 1, height: 28, background: "var(--border)" }} />
        <button onClick={() => { persistMode("overlay"); void showOverlay(); }} title="Switch to Overlay (Marvex presence)" style={{ ...iconBtn, width: 44, height: 44, borderRadius: 12 }}><Radio size={18} /></button>
      </footer>
    </div>
  );
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
