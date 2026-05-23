import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { MessageSquare, History, SlidersHorizontal, Mic, MicOff, Radio } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { listen } from "@/lib/tauriBridge";
import { type TurnStage, type UiDirective } from "@/lib/localTurn";
import { getShellRuntimeConfig, showOverlay, submitChatTurn, openControlPlane, type ShellRuntimeConfig } from "@/lib/shellCommands";
import { persistMode } from "@/lib/modeStore";
import { idleAssistantState, normalizeAssistantState, statusLabel, type AssistantStateEvent, type AssistantStatusKind } from "@/lib/assistantState";
import { outcomeFromTurnResult, outcomeFromError } from "@/lib/turnOutcome";
import { getActiveSessionId, loadMessages, saveMessages, newSession, setActiveSession, listSessions, type SessionMeta, type StoredMessage } from "@/lib/sessionStore";

import { LimelightNav } from "@/components/dock";
import { Loader } from "@/components/loader";
import { AppleHelloEnglishEffect } from "@/components/apple-hello-effect";
import { Typewriter } from "@/components/typewriter";
import { ScrambleText } from "@/components/scramble-text";
import ChatInput from "@/components/prompt-input-dynamic-grow";
import { Orb } from "@/components/chat-messages-for-ui/agent-simple-orb";
import { Message, MessageContent } from "@/components/ui/message";
import { RichMessage } from "@/components/marvex/RichMessage";
import { BackgroundPlus } from "@/components/ui/background-plus";
import { Status, StatusIndicator, StatusLabel } from "@/components/status-for-ui/status";
import { Button } from "@/components/ui/button";

type ChatMessage = { role: "user" | "assistant" | "system"; text: string; stages?: TurnStage[]; directives?: UiDirective[] };
type TabId = "chat" | "sessions";

const TAB_TITLES: Record<TabId, string> = {
  chat: "Assistant Chat",
  sessions: "Sessions",
};

function agentStateFromStatus(status: AssistantStatusKind): "thinking" | "listening" | "talking" | null {
  if (status === "listening") return "listening";
  if (status === "talking") return "talking";
  if (status === "thinking" || status === "working" || status === "using_tools" || status === "mcp" || status === "skills" || status === "searching_web") return "thinking";
  return null;
}

export function ChatApp() {
  const [config, setConfig] = useState<ShellRuntimeConfig | null>(null);
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const sessionIdRef = useRef<string>(getActiveSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const restored = loadMessages(sessionIdRef.current) as ChatMessage[];
    return restored.length ? restored : [{ role: "system", text: "Marvex is ready. How can I help?" }];
  });
  const [pending, setPending] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const [showHello, setShowHello] = useState(true);
  const [micActive, setMicActive] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const statusText = statusLabel(state.status);

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
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  // Persist the conversation so it survives shell close/reopen.
  useEffect(() => {
    saveMessages(sessionIdRef.current, messages as StoredMessage[]);
  }, [messages]);

  const send = useCallback(async (text: string) => {
    if (!text.trim() || pending) return;
    setPending(true);
    setMessages((prev) => [...prev, { role: "user", text }]);
    try {
      const result = await submitChatTurn(text, { session_id: sessionIdRef.current });
      const outcome = outcomeFromTurnResult(result);
      setMessages((prev) => [...prev, { role: "assistant", text: outcome.text, stages: outcome.stages, directives: outcome.directives }]);
    } catch (error) {
      const outcome = outcomeFromError(error);
      setMessages((prev) => [...prev, { role: "assistant", text: outcome.text }]);
    } finally {
      setPending(false);
    }
  }, [pending]);

  const navItems = useMemo(() => [
    { id: "chat", icon: <MessageSquare />, label: "Chat", onClick: () => setActiveTab("chat") },
    { id: "sessions", icon: <History />, label: "Sessions", onClick: () => setActiveTab("sessions") },
    { id: "control", icon: <SlidersHorizontal />, label: "Control Plane", onClick: () => void openControlPlane() },
  ], []);

  const startNewSession = useCallback(() => {
    const id = newSession();
    sessionIdRef.current = id;
    setMessages([{ role: "system", text: "New chat started." }]);
    setActiveTab("chat");
  }, []);

  const openSession = useCallback((id: string) => {
    setActiveSession(id);
    sessionIdRef.current = id;
    const restored = loadMessages(id) as ChatMessage[];
    setMessages(restored.length ? restored : [{ role: "system", text: "Marvex is ready. How can I help?" }]);
    setActiveTab("chat");
  }, []);

  const activeNavIndex = Math.max(0, navItems.findIndex((n) => n.id === activeTab));
  const orbState = agentStateFromStatus(state.status);

  return (
    <div className="flex flex-col h-screen min-h-0 relative z-[1]" style={{ background: "transparent", color: "var(--foreground)" }}>
      <BackgroundPlus plusColor="#ffe0c2" plusSize={56} fade={false} className="pointer-events-none opacity-35" />
      {/* Topbar */}
      <header style={{ minHeight: 60, padding: "10px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", background: "color-mix(in srgb, var(--card) 70%, transparent)", backdropFilter: "blur(16px)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <img src="/assets/Marvex_App_192.png" alt="Marvex" style={{ width: 30, height: 30, borderRadius: 8, objectFit: "contain" }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          <div>
            <ScrambleText as="h1" text={TAB_TITLES[activeTab]} className="m-0 text-[17px] font-bold" style={{ color: "var(--foreground)" }} />
            <p style={{ margin: "1px 0 0", color: "var(--muted-foreground)", fontSize: 11 }}>
              {config ? `${config.core_base_url}` : "Connecting..."}
            </p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {(pending || state.status !== "idle") && <Loader variant="circular" size="sm" />}
          <Status status={state.status === "idle" ? "online" : "degraded"}>
            <StatusIndicator />
            <StatusLabel>{state.status === "idle" ? "Ready" : statusText}</StatusLabel>
          </Status>
        </div>
      </header>

      {/* Content */}
      <div style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column", position: "relative" }}>
        <AnimatePresence mode="wait">
          {activeTab === "chat" && (
            <motion.div key="chat" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
              {/* Hello splash (first run of the chat tab) */}
              <AnimatePresence>
                {showHello && (
                  <motion.div exit={{ opacity: 0, scale: 0.9 }} transition={{ duration: 0.5 }} className="absolute inset-0 flex flex-col items-center justify-center gap-4 z-10 pointer-events-none" style={{ background: "var(--background)" }}>
                    <AppleHelloEnglishEffect className="h-16" style={{ color: "var(--primary)" }} speed={1.1} onAnimationComplete={() => setTimeout(() => setShowHello(false), 500)} />
                    <ScrambleText text="I am Marvex" className="text-sm tracking-[0.35em] uppercase" style={{ color: "var(--muted-foreground)" }} speed={45} />
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Messages */}
              <div style={{ flex: 1, overflow: "auto", padding: "18px 20px", display: "flex", flexDirection: "column", gap: 10, minHeight: 0 }}>
                {messages.map((msg, idx) => (
                  <Message key={`${msg.role}-${idx}`} from={msg.role === "user" ? "user" : "assistant"}>
                    {msg.role === "assistant" ? (
                      <MessageContent variant="flat" className="w-full max-w-[88%]">
                        <RichMessage text={msg.text} stages={msg.stages} directives={msg.directives} />
                      </MessageContent>
                    ) : (
                      <MessageContent variant={msg.role === "system" ? "flat" : "contained"}>
                        {msg.text}
                      </MessageContent>
                    )}
                    {msg.role === "assistant" && (
                      <div className="size-8 overflow-hidden rounded-full ring-1 ring-border shrink-0">
                        <Orb className="h-full w-full" agentState={orbState} />
                      </div>
                    )}
                  </Message>
                ))}
                {pending && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0" }}>
                    <div className="size-8 overflow-hidden rounded-full ring-1 ring-border shrink-0">
                      <Orb className="h-full w-full" agentState="thinking" />
                    </div>
                    <Loader variant="loading-dots" text={statusText} />
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* IDLE prompt area */}
              {!pending && messages.length <= 1 && !showHello && (
                <div style={{ padding: "0 20px 6px", textAlign: "center" }}>
                  <Typewriter
                    text={["How can I help you today?", "Search the web, write a file, plan a task...", "Ask me anything."]}
                    speed={55} deleteSpeed={25} waitTime={2200} loop
                    className="text-sm"
                  />
                </div>
              )}

              {/* Composer */}
              <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", background: "color-mix(in srgb, var(--card) 70%, transparent)", backdropFilter: "blur(16px)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <button
                    title="Microphone"
                    onClick={() => setMicActive((v) => !v)}
                    style={{ width: 40, height: 40, borderRadius: 10, border: "1px solid var(--border)", background: micActive ? "var(--primary)" : "var(--secondary)", color: micActive ? "var(--primary-foreground)" : "var(--foreground)", display: "grid", placeItems: "center", cursor: "pointer" }}
                  >
                    {micActive ? <MicOff size={16} /> : <Mic size={16} />}
                  </button>
                  <div style={{ flex: 1 }}>
                    <ChatInput
                      placeholder="Ask Marvex..."
                      disabled={pending}
                      onSubmit={send}
                      textColor="var(--foreground)"
                      backgroundOpacity={0.06}
                    />
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === "sessions" && (
            <motion.div key="sessions" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ flex: 1, overflow: "auto", padding: 20 }}>
              <div style={{ maxWidth: 640, display: "flex", flexDirection: "column", gap: 10 }}>
                <Button size="sm" variant="outline" onClick={startNewSession}>New chat</Button>
                {listSessions().map((s: SessionMeta) => (
                  <button
                    key={s.id}
                    onClick={() => openSession(s.id)}
                    style={{ textAlign: "left", padding: "10px 12px", borderRadius: 10, background: s.id === sessionIdRef.current ? "var(--accent)" : "var(--secondary)", border: "1px solid var(--border)", cursor: "pointer", color: "var(--foreground)" }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{s.title || "New chat"}</div>
                    <div style={{ fontSize: 11, color: "var(--muted-foreground)" }}>{new Date(s.updatedAt).toLocaleString()}</div>
                  </button>
                ))}
                {listSessions().length === 0 && (
                  <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>No saved sessions yet.</span>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom dock */}
      <footer style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, padding: "10px 16px", borderTop: "1px solid var(--border)", background: "color-mix(in srgb, var(--card) 70%, transparent)", backdropFilter: "blur(16px)" }}>
        <LimelightNav
          items={navItems}
          defaultActiveIndex={activeNavIndex}
          onTabChange={(idx) => {
            const item = navItems[idx];
            if (item.id === "control") { void openControlPlane(); return; }
            setActiveTab(item.id as TabId);
          }}
        />
        <div style={{ width: 1, height: 28, background: "var(--border)" }} />
        <button
          onClick={() => { persistMode("overlay"); void showOverlay(); }}
          title="Switch to Overlay (Marvex presence)"
          style={{ width: 44, height: 44, borderRadius: 12, background: "var(--secondary)", border: "1px solid var(--border)", color: "var(--foreground)", display: "grid", placeItems: "center", cursor: "pointer" }}
        >
          <Radio size={18} />
        </button>
      </footer>
    </div>
  );
}
