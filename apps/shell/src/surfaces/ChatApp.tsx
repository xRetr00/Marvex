import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { MessageSquare, SlidersHorizontal, Mic, MicOff, Radio, History, X, RefreshCw, Plus, Ear } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { listen } from "@/lib/tauriBridge";
import { type TurnStage, type UiDirective } from "@/lib/localTurn";
import { getShellRuntimeConfig, showOverlay, submitChatTurn, openControlPlane, getSetupStatus, getSupervisorStatus, controlRequest, startBackend, type ShellRuntimeConfig } from "@/lib/shellCommands";
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

type WakewordState = "unknown" | "running" | "enabled" | "not_ready" | "disabled";

interface BackendStatus {
  phase: string;
  ready: boolean;
  launched: boolean;
  services: Record<string, string>;
  wakeword: WakewordState;
}

const FAILED_PHASES = new Set(["venv_failed", "install_failed", "install_incomplete", "uv_unavailable", "failed"]);

function agentStateFromStatus(status: AssistantStatusKind): "thinking" | "listening" | "talking" | null {
  if (status === "listening") return "listening";
  if (status === "talking") return "talking";
  if (status === "thinking" || status === "working" || status === "using_tools" || status === "mcp" || status === "skills" || status === "searching_web") return "thinking";
  return null;
}

function serviceOk(value: string): boolean {
  return value.startsWith("running") || value === "ready" || value === "dev";
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
  const [micActive, setMicActive] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Backend bring-up: the chat stays behind a startup screen until the backend
  // is ready, and the Apple hello always plays on open.
  const [backend, setBackend] = useState<BackendStatus | null>(null);
  const [helloDone, setHelloDone] = useState(false);
  const [booted, setBooted] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void getShellRuntimeConfig().then(setConfig).catch(() => setConfig(null));
    let cleanup: VoidFunction | undefined;
    void listen("assistant-state", (event) => {
      try { setState(normalizeAssistantState(event.payload)); }
      catch { setState(idleAssistantState); }
    }).then((unlisten) => { cleanup = unlisten; });
    return () => cleanup?.();
  }, []);

  // Poll backend readiness + wakeword status (fast while booting, slow after).
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      const [setup, services, voice] = await Promise.allSettled([
        getSetupStatus(),
        getSupervisorStatus(),
        controlRequest("/voice/worker", "GET"),
      ]);
      if (cancelled) return;
      const svc = services.status === "fulfilled" ? services.value : {};
      let wake: WakewordState = "unknown";
      if (voice.status === "fulfilled" && voice.value && typeof voice.value === "object") {
        const w = (voice.value as { wakeword_status?: string; lifecycle_state?: string });
        if (w.wakeword_status) wake = (w.wakeword_status as WakewordState);
        else if (w.lifecycle_state === "running") wake = "running";
      } else if (typeof svc.voice_worker === "string" && svc.voice_worker.startsWith("running")) {
        wake = "running";
      }
      const next: BackendStatus = {
        phase: setup.status === "fulfilled" ? setup.value.runtime_phase : "unknown",
        ready: setup.status === "fulfilled" ? setup.value.ready : false,
        launched: setup.status === "fulfilled" ? setup.value.launched : false,
        services: svc,
        wakeword: wake,
      };
      setBackend(next);
      timer = setTimeout(() => void tick(), next.ready ? 5000 : 1200);
    };
    void tick();
    return () => { cancelled = true; clearTimeout(timer); };
  }, []);

  // Reveal the chat once the backend is ready AND the hello has played.
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
    { id: "chat", icon: <MessageSquare />, label: "Chat", onClick: () => undefined },
    { id: "sessions", icon: <History />, label: "Sessions", onClick: () => setSidebarOpen((v) => !v) },
    { id: "control", icon: <SlidersHorizontal />, label: "Control Plane", onClick: () => void openControlPlane() },
  ], []);

  const startNewSession = useCallback(() => {
    const id = newSession();
    sessionIdRef.current = id;
    setMessages([{ role: "system", text: "New chat started." }]);
    setSidebarOpen(false);
  }, []);

  const openSession = useCallback((id: string) => {
    setActiveSession(id);
    sessionIdRef.current = id;
    const restored = loadMessages(id) as ChatMessage[];
    setMessages(restored.length ? restored : [{ role: "system", text: "Marvex is ready. How can I help?" }]);
    setSidebarOpen(false);
  }, []);

  const orbState = agentStateFromStatus(state.status);

  if (!booted) {
    return <StartupScreen backend={backend} onHelloDone={() => setHelloDone(true)} onRetry={() => void startBackend().catch(() => undefined)} />;
  }

  return (
    <div className="flex flex-col h-screen min-h-0 relative z-[1]" style={{ background: "transparent", color: "var(--foreground)" }}>
      <BackgroundPlus plusColor="#ffe0c2" plusSize={56} fade={false} className="pointer-events-none opacity-35" />
      {/* Topbar */}
      <header style={{ minHeight: 60, padding: "10px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", background: "color-mix(in srgb, var(--card) 70%, transparent)", backdropFilter: "blur(16px)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => setSidebarOpen((v) => !v)} title="Sessions" style={{ width: 34, height: 34, borderRadius: 8, border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--foreground)", display: "grid", placeItems: "center", cursor: "pointer" }}>
            <History size={16} />
          </button>
          <img src="/assets/Marvex_App_192.png" alt="Marvex" style={{ width: 30, height: 30, borderRadius: 8, objectFit: "contain" }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          <div>
            <ScrambleText as="h1" text="Assistant Chat" className="m-0 text-[17px] font-bold" style={{ color: "var(--foreground)" }} />
            <p style={{ margin: "1px 0 0", color: "var(--muted-foreground)", fontSize: 11 }}>
              {config ? `${config.core_base_url}` : "Connecting..."}
            </p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <WakewordBadge state={backend?.wakeword ?? "unknown"} />
          {(pending || state.status !== "idle") && <Loader variant="circular" size="sm" />}
          <Status status={state.status === "idle" ? "online" : "degraded"}>
            <StatusIndicator />
            <StatusLabel>{state.status === "idle" ? "Ready" : statusLabel(state.status)}</StatusLabel>
          </Status>
        </div>
      </header>

      {/* Content + sessions sidebar */}
      <div style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", position: "relative" }}>
        <AnimatePresence>
          {sidebarOpen && (
            <motion.aside
              initial={{ x: -280, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: -280, opacity: 0 }}
              transition={{ type: "spring", duration: 0.35, bounce: 0.1 }}
              style={{ position: "absolute", inset: "0 auto 0 0", width: 280, zIndex: 5, background: "color-mix(in srgb, var(--card) 92%, transparent)", backdropFilter: "blur(16px)", borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column" }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderBottom: "1px solid var(--border)" }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Sessions</span>
                <button onClick={() => setSidebarOpen(false)} style={{ background: "none", border: "none", color: "var(--muted-foreground)", cursor: "pointer", display: "grid", placeItems: "center" }}><X size={16} /></button>
              </div>
              <div style={{ padding: 10 }}>
                <Button size="sm" variant="outline" className="w-full" onClick={startNewSession}><Plus size={14} className="mr-1" /> New chat</Button>
              </div>
              <div style={{ flex: 1, overflow: "auto", padding: "0 10px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
                {listSessions().map((s: SessionMeta) => (
                  <button key={s.id} onClick={() => openSession(s.id)}
                    style={{ textAlign: "left", padding: "8px 10px", borderRadius: 10, background: s.id === sessionIdRef.current ? "var(--accent)" : "var(--secondary)", border: "1px solid var(--border)", cursor: "pointer", color: "var(--foreground)" }}>
                    <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.title || "New chat"}</div>
                    <div style={{ fontSize: 10, color: "var(--muted-foreground)" }}>{new Date(s.updatedAt).toLocaleString()}</div>
                  </button>
                ))}
                {listSessions().length === 0 && <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>No saved sessions yet.</span>}
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
          {/* Messages */}
          <div style={{ flex: 1, overflow: "auto", padding: "18px 20px", display: "flex", flexDirection: "column", gap: 10, minHeight: 0 }}>
            {messages.map((msg, idx) => (
              <Message key={`${msg.role}-${idx}`} from={msg.role === "user" ? "user" : "assistant"}>
                {msg.role === "assistant" ? (
                  <MessageContent variant="flat" className="w-full max-w-[88%]">
                    <RichMessage text={msg.text} stages={msg.stages} directives={msg.directives} />
                  </MessageContent>
                ) : (
                  <MessageContent variant={msg.role === "system" ? "flat" : "contained"}>{msg.text}</MessageContent>
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
                <Loader variant="loading-dots" text="Marvex is thinking" />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* IDLE prompt area */}
          {!pending && messages.length <= 1 && (
            <div style={{ padding: "0 20px 6px", textAlign: "center" }}>
              <Typewriter text={["How can I help you today?", "Search the web, write a file, plan a task...", "Ask me anything."]} speed={55} deleteSpeed={25} waitTime={2200} loop className="text-sm" />
            </div>
          )}

          {/* Composer */}
          <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", background: "color-mix(in srgb, var(--card) 70%, transparent)", backdropFilter: "blur(16px)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button title="Microphone" onClick={() => setMicActive((v) => !v)}
                style={{ width: 40, height: 40, borderRadius: 10, border: "1px solid var(--border)", background: micActive ? "var(--primary)" : "var(--secondary)", color: micActive ? "var(--primary-foreground)" : "var(--foreground)", display: "grid", placeItems: "center", cursor: "pointer" }}>
                {micActive ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
              <div style={{ flex: 1 }}>
                <ChatInput placeholder="Ask Marvex..." disabled={pending} onSubmit={send} textColor="var(--foreground)" backgroundOpacity={0.06} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom dock */}
      <footer style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, padding: "10px 16px", borderTop: "1px solid var(--border)", background: "color-mix(in srgb, var(--card) 70%, transparent)", backdropFilter: "blur(16px)" }}>
        <LimelightNav
          items={navItems}
          defaultActiveIndex={0}
          onTabChange={(idx) => navItems[idx]?.onClick()}
        />
        <div style={{ width: 1, height: 28, background: "var(--border)" }} />
        <button onClick={() => { persistMode("overlay"); void showOverlay(); }} title="Switch to Overlay (Marvex presence)"
          style={{ width: 44, height: 44, borderRadius: 12, background: "var(--secondary)", border: "1px solid var(--border)", color: "var(--foreground)", display: "grid", placeItems: "center", cursor: "pointer" }}>
          <Radio size={18} />
        </button>
      </footer>
    </div>
  );
}

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

function StartupScreen({ backend, onHelloDone, onRetry }: { backend: BackendStatus | null; onHelloDone: () => void; onRetry: () => void }) {
  const phase = backend?.phase ?? "starting";
  const failed = FAILED_PHASES.has(phase);
  const services = backend?.services ?? {};
  const serviceNames = Object.keys(services).filter((n) => n !== "runtime");
  return (
    <div className="flex flex-col items-center justify-center h-screen gap-6 relative" style={{ background: "var(--background)", color: "var(--foreground)" }}>
      <BackgroundPlus plusColor="#ffe0c2" plusSize={56} fade className="pointer-events-none opacity-25" />
      <AppleHelloEnglishEffect className="h-16" style={{ color: "var(--primary)" }} speed={1.1} onAnimationComplete={onHelloDone} />
      <ScrambleText text="I am Marvex" className="text-sm tracking-[0.35em] uppercase" style={{ color: "var(--muted-foreground)" }} speed={45} />

      <div style={{ width: 340, maxWidth: "82vw", display: "flex", flexDirection: "column", gap: 8, marginTop: 6 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, color: "var(--muted-foreground)", fontSize: 12 }}>
          {!backend?.ready && !failed && <Loader variant="circular" size="sm" />}
          <span>{failed ? "Setup needed" : backend?.ready ? "Ready" : `Bringing up backend… (${phase})`}</span>
        </div>
        {serviceNames.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 6 }}>
            {serviceNames.map((name) => {
              const ok = serviceOk(services[name]);
              return (
                <div key={name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "6px 9px", borderRadius: 8, background: "var(--secondary)", border: "1px solid var(--border)", fontSize: 11 }}>
                  <span style={{ textTransform: "capitalize" }}>{name.replace(/_/g, " ")}</span>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: ok ? "#34d399" : "#f59e0b" }} />
                </div>
              );
            })}
          </div>
        )}
        {failed && (
          <Button size="sm" variant="outline" className="mx-auto mt-2" onClick={onRetry}><RefreshCw size={14} className="mr-1" /> Retry setup</Button>
        )}
      </div>
    </div>
  );
}
