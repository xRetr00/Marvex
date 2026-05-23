import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { MessageSquare, Settings, Package, Mic, MicOff, Radio, Sparkles, RefreshCw, AlertTriangle, Activity } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { listen } from "@/lib/tauriBridge";
import { finalTextFromTurnResult, stagesFromTurnResult, uiDirectivesFromTurnResult, type TurnStage, type UiDirective } from "@/lib/localTurn";
import { getShellRuntimeConfig, showSpotlight, submitChatTurn, getSupervisorStatus, getSetupStatus, type ShellRuntimeConfig } from "@/lib/shellCommands";
import { idleAssistantState, normalizeAssistantState, statusLabel, type AssistantStateEvent, type AssistantStatusKind } from "@/lib/assistantState";
import { fetchDeps, installDep, type Dep } from "@/lib/depsClient";
import { fetchPendingApprovals } from "@/lib/controlPlaneClient";
import type { AppMode } from "@/lib/modeStore";

import { LimelightNav } from "@/components/dock";
import { Loader } from "@/components/loader";
import { Badge } from "@/components/ui/badge";
import { AppleHelloEnglishEffect } from "@/components/apple-hello-effect";
import { Typewriter } from "@/components/typewriter";
import { ScrambleText } from "@/components/scramble-text";
import ChatInput from "@/components/prompt-input-dynamic-grow";
import { Orb } from "@/components/chat-messages-for-ui/agent-simple-orb";
import { Message, MessageContent } from "@/components/ui/message";
import { RichMessage } from "@/components/marvex/RichMessage";
import AnimatedProgressBar from "@/components/animated-progress-bar";
import SystemMonitor from "@/components/system-monitor/system-monitor";
import {
  VoiceSelector, VoiceSelectorTrigger, VoiceSelectorContent, VoiceSelectorInput,
  VoiceSelectorList, VoiceSelectorEmpty, VoiceSelectorGroup, VoiceSelectorItem,
  VoiceSelectorName, VoiceSelectorDescription, VoiceSelectorAttributes,
  VoiceSelectorAccent, VoiceSelectorGender, VoiceSelectorPreview,
} from "@/components/voice-selector";
import { Status, StatusIndicator, StatusLabel } from "@/components/status-for-ui/status";
import { Button } from "@/components/ui/button";

type ChatMessage = { role: "user" | "assistant" | "system"; text: string; stages?: TurnStage[]; directives?: UiDirective[] };
type TabId = "chat" | "settings" | "deps";
type DepsState = "loading" | "ready" | "error";

interface ChatAppProps {
  mode: AppMode;
  onModeChange: (mode: AppMode) => void;
}

const TAB_TITLES: Record<TabId, string> = {
  chat: "Assistant Chat",
  settings: "Settings",
  deps: "Dependencies",
};

const FEATURE_LABELS: Record<string, string> = {
  tts: "Text-to-Speech",
  stt: "Speech-to-Text",
  wakeword: "Wake Word",
  web_search: "Web Search",
  browser: "Browser",
  embeddings: "Embeddings",
};

const VOICES = [
  { id: "kokoro-default", name: "Kokoro", gender: "female" as const, accent: "american", description: "Natural neural TTS" },
  { id: "piper-en", name: "Piper", gender: "male" as const, accent: "british", description: "Fast local TTS" },
  { id: "kokoro-ja", name: "Kokoro (JP)", gender: "female" as const, accent: "japanese", description: "Japanese neural TTS" },
];

interface ControlPlaneState {
  runtimePhase: string;
  services: Record<string, string>;
  approvals: number;
  ready: boolean;
}

function agentStateFromStatus(status: AssistantStatusKind): "thinking" | "listening" | "talking" | null {
  if (status === "listening") return "listening";
  if (status === "talking") return "talking";
  if (status === "thinking" || status === "working" || status === "using_tools" || status === "mcp" || status === "skills" || status === "searching_web") return "thinking";
  return null;
}

export function ChatApp({ mode, onModeChange }: ChatAppProps) {
  const [config, setConfig] = useState<ShellRuntimeConfig | null>(null);
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "system", text: "Marvex is ready. How can I help?" },
  ]);
  const [pending, setPending] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const [showHello, setShowHello] = useState(true);
  const [micActive, setMicActive] = useState(false);

  // Deps state
  const [deps, setDeps] = useState<Dep[]>([]);
  const [features, setFeatures] = useState<Record<string, boolean>>({});
  const [depsState, setDepsState] = useState<DepsState>("loading");
  const [depsReload, setDepsReload] = useState(0);
  const [installingDep, setInstallingDep] = useState<string | null>(null);
  const [depProgress, setDepProgress] = useState<Record<string, number>>({});

  // Settings / control plane
  const [selectedVoice, setSelectedVoice] = useState<string>("kokoro-default");
  const [controlPlane, setControlPlane] = useState<ControlPlaneState | null>(null);

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

  // Deps fetch — fail-fast so the panel never spins forever.
  useEffect(() => {
    let cancelled = false;
    setDepsState("loading");
    const timer = setTimeout(() => { if (!cancelled) setDepsState((s) => (s === "loading" ? "error" : s)); }, 12000);
    void fetchDeps()
      .then((data) => {
        if (cancelled) return;
        setDeps(data.deps);
        setFeatures(data.features);
        setDepsState("ready");
      })
      .catch(() => { if (!cancelled) setDepsState("error"); });
    return () => { cancelled = true; clearTimeout(timer); };
  }, [depsReload]);

  // Control plane snapshot — refresh while the Settings tab is open.
  useEffect(() => {
    if (activeTab !== "settings") return;
    let cancelled = false;
    const load = async () => {
      const [setup, services, approvals] = await Promise.allSettled([
        getSetupStatus(),
        getSupervisorStatus(),
        fetchPendingApprovals(),
      ]);
      if (cancelled) return;
      setControlPlane({
        runtimePhase: setup.status === "fulfilled" ? setup.value.runtime_phase : "unknown",
        ready: setup.status === "fulfilled" ? setup.value.ready : false,
        services: services.status === "fulfilled" ? services.value : {},
        approvals: approvals.status === "fulfilled" ? approvals.value.length : 0,
      });
    };
    void load();
    const interval = setInterval(() => void load(), 4000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [activeTab]);

  const ttsAvailable = features.tts !== false;
  const sttAvailable = features.stt !== false;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  const send = useCallback(async (text: string) => {
    if (!text.trim() || pending) return;
    setPending(true);
    setMessages((prev) => [...prev, { role: "user", text }]);
    try {
      const result = await submitChatTurn(text);
      setMessages((prev) => [...prev, { role: "assistant", text: finalTextFromTurnResult(result), stages: stagesFromTurnResult(result), directives: uiDirectivesFromTurnResult(result) }]);
    } catch (error) {
      setMessages((prev) => [...prev, { role: "assistant", text: error instanceof Error ? error.message : "Request failed." }]);
    } finally {
      setPending(false);
    }
  }, [pending]);

  const handleInstallDep = useCallback(async (id: string) => {
    setInstallingDep(id);
    setDepProgress((prev) => ({ ...prev, [id]: 0 }));
    const interval = setInterval(() => {
      setDepProgress((prev) => ({ ...prev, [id]: Math.min((prev[id] ?? 0) + 8, 90) }));
    }, 300);
    try {
      const result = await installDep(id);
      clearInterval(interval);
      setDepProgress((prev) => ({ ...prev, [id]: result.status === "installed" ? 100 : 0 }));
      if (result.status === "installed") {
        setDeps((prev) => prev.map((d) => d.id === id ? { ...d, installed: true } : d));
        const updated = await fetchDeps().catch(() => null);
        if (updated) { setDeps(updated.deps); setFeatures(updated.features); }
      }
    } catch {
      clearInterval(interval);
      setDepProgress((prev) => ({ ...prev, [id]: 0 }));
    } finally {
      setInstallingDep(null);
    }
  }, []);

  const navItems = useMemo(() => [
    { id: "chat", icon: <MessageSquare />, label: "Chat", onClick: () => setActiveTab("chat") },
    { id: "settings", icon: <Settings />, label: "Settings", onClick: () => setActiveTab("settings") },
    { id: "deps", icon: <Package />, label: "Deps", onClick: () => setActiveTab("deps") },
  ], []);
  const activeNavIndex = Math.max(0, navItems.findIndex((n) => n.id === activeTab));
  const orbState = agentStateFromStatus(state.status);

  return (
    <div className="flex flex-col h-screen min-h-0" style={{ background: "var(--background)", color: "var(--foreground)" }}>
      {/* Topbar */}
      <header style={{ minHeight: 60, padding: "10px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", background: "var(--card)" }}>
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
              <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", background: "var(--card)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <button
                    title={sttAvailable ? "Microphone" : "STT unavailable"}
                    disabled={!sttAvailable}
                    onClick={() => setMicActive((v) => !v)}
                    style={{ width: 40, height: 40, borderRadius: 10, border: "1px solid var(--border)", background: micActive ? "var(--primary)" : "var(--secondary)", color: micActive ? "var(--primary-foreground)" : "var(--foreground)", display: "grid", placeItems: "center", cursor: sttAvailable ? "pointer" : "not-allowed", opacity: sttAvailable ? 1 : 0.4 }}
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

          {activeTab === "settings" && (
            <motion.div key="settings" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ flex: 1, overflow: "auto", padding: 20 }}>
              <div style={{ maxWidth: 640, display: "flex", flexDirection: "column", gap: 18 }}>
                {/* Control Plane */}
                <section style={{ background: "var(--card)", borderRadius: 14, padding: 18, border: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                    <Activity size={16} style={{ color: "var(--primary)" }} />
                    <ScrambleText as="h2" text="Control Plane" className="text-[15px] font-semibold" />
                  </div>
                  {controlPlane ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        <Badge variant={controlPlane.ready ? "default" : "destructive"}>
                          Runtime: {controlPlane.runtimePhase}
                        </Badge>
                        <Badge variant={controlPlane.approvals > 0 ? "destructive" : "secondary"}>
                          Pending approvals: {controlPlane.approvals}
                        </Badge>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 8 }}>
                        {Object.entries(controlPlane.services).map(([name, status]) => {
                          const ok = status.startsWith("running") || status === "ready" || status === "dev";
                          return (
                            <div key={name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "8px 10px", borderRadius: 10, background: "var(--secondary)", border: "1px solid var(--border)" }}>
                              <span style={{ fontSize: 12, fontWeight: 500, textTransform: "capitalize" }}>{name}</span>
                              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--muted-foreground)" }}>
                                <span style={{ width: 7, height: 7, borderRadius: "50%", background: ok ? "#34d399" : "#e54d2e" }} />
                                {status}
                              </span>
                            </div>
                          );
                        })}
                        {Object.keys(controlPlane.services).length === 0 && (
                          <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>No services reported.</span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--muted-foreground)", fontSize: 13 }}>
                      <Loader variant="circular" size="sm" /> Reading control plane...
                    </div>
                  )}
                </section>

                {/* Voice selector */}
                <section style={{ background: "var(--card)", borderRadius: 14, padding: 18, border: "1px solid var(--border)" }}>
                  <h2 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600 }}>TTS Voice</h2>
                  {!ttsAvailable && (
                    <div style={{ padding: "8px 12px", background: "color-mix(in srgb, var(--destructive) 14%, transparent)", border: "1px solid color-mix(in srgb, var(--destructive) 35%, transparent)", borderRadius: 8, marginBottom: 12, color: "var(--destructive)", fontSize: 12 }}>
                      TTS dependency missing. Install it in the Deps tab.
                    </div>
                  )}
                  <VoiceSelector value={selectedVoice} onValueChange={(v) => v && setSelectedVoice(v)}>
                    <VoiceSelectorTrigger asChild>
                      <Button variant="outline" disabled={!ttsAvailable} className="w-full justify-between">
                        {VOICES.find((v) => v.id === selectedVoice)?.name ?? "Select voice..."}
                      </Button>
                    </VoiceSelectorTrigger>
                    <VoiceSelectorContent>
                      <VoiceSelectorInput placeholder="Search voices..." />
                      <VoiceSelectorList>
                        <VoiceSelectorEmpty>No voices found.</VoiceSelectorEmpty>
                        <VoiceSelectorGroup heading="Available Voices">
                          {VOICES.map((voice) => (
                            <VoiceSelectorItem key={voice.id} value={voice.id} className="flex items-center gap-3">
                              <VoiceSelectorPreview onPlay={() => undefined} />
                              <div className="flex flex-1 flex-col">
                                <VoiceSelectorName>{voice.name}</VoiceSelectorName>
                                <VoiceSelectorDescription>{voice.description}</VoiceSelectorDescription>
                              </div>
                              <VoiceSelectorAttributes className="gap-2">
                                <VoiceSelectorGender value={voice.gender} />
                                <VoiceSelectorAccent value={voice.accent} />
                              </VoiceSelectorAttributes>
                            </VoiceSelectorItem>
                          ))}
                        </VoiceSelectorGroup>
                      </VoiceSelectorList>
                    </VoiceSelectorContent>
                  </VoiceSelector>
                </section>

                {/* System monitor */}
                <section>
                  <h2 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600 }}>System Monitor</h2>
                  <SystemMonitor />
                </section>
              </div>
            </motion.div>
          )}

          {activeTab === "deps" && (
            <motion.div key="deps" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ flex: 1, overflow: "auto", padding: 20 }}>
              <div style={{ maxWidth: 700, display: "flex", flexDirection: "column", gap: 16 }}>
                {/* Feature status */}
                {Object.keys(features).length > 0 && (
                  <section style={{ background: "var(--card)", borderRadius: 14, padding: 16, border: "1px solid var(--border)" }}>
                    <h2 style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 600, color: "var(--muted-foreground)" }}>Feature Status</h2>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      {Object.entries(features).map(([key, available]) => (
                        <Badge key={key} variant={available ? "default" : "destructive"}>
                          {FEATURE_LABELS[key] ?? key}: {available ? "OK" : "unavailable"}
                        </Badge>
                      ))}
                    </div>
                  </section>
                )}

                {/* Dep list */}
                <section style={{ background: "var(--card)", borderRadius: 14, border: "1px solid var(--border)", overflow: "hidden" }}>
                  <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)", fontWeight: 600, fontSize: 14, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    Models &amp; Dependencies
                    <Button size="sm" variant="ghost" onClick={() => setDepsReload((n) => n + 1)} title="Refresh">
                      <RefreshCw size={14} />
                    </Button>
                  </div>
                  {depsState === "loading" && (
                    <div style={{ padding: 24, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>
                      <Loader variant="circular" size="md" />
                      <p style={{ marginTop: 8 }}>Loading dependencies...</p>
                    </div>
                  )}
                  {depsState === "error" && (
                    <div style={{ padding: 24, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13, display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
                      <AlertTriangle size={22} style={{ color: "var(--destructive)" }} />
                      <p style={{ margin: 0 }}>Couldn't reach the control plane. The backend may still be starting.</p>
                      <Button size="sm" variant="outline" onClick={() => setDepsReload((n) => n + 1)}>Retry</Button>
                    </div>
                  )}
                  {depsState === "ready" && deps.length === 0 && (
                    <div style={{ padding: 24, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>
                      All dependencies are installed.
                    </div>
                  )}
                  {depsState === "ready" && deps.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column" }}>
                      {deps.map((dep) => {
                        const isInstalling = installingDep === dep.id;
                        const progress = depProgress[dep.id] ?? 0;
                        return (
                          <div key={dep.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: 13, fontWeight: 500 }}>{dep.label}</div>
                              <div style={{ fontSize: 11, color: "var(--muted-foreground)" }}>{dep.group}</div>
                              {isInstalling && <AnimatedProgressBar value={progress} color="var(--primary)" className="mt-2" />}
                            </div>
                            {dep.installed ? (
                              <Badge variant="default">Installed</Badge>
                            ) : (
                              <Button size="sm" variant="outline" disabled={isInstalling} onClick={() => void handleInstallDep(dep.id)}>
                                {isInstalling ? <Loader variant="circular" size="sm" /> : "Download"}
                              </Button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </section>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom dock */}
      <footer style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, padding: "10px 16px", borderTop: "1px solid var(--border)", background: "var(--card)" }}>
        <LimelightNav
          items={navItems}
          defaultActiveIndex={activeNavIndex}
          onTabChange={(idx) => setActiveTab(navItems[idx].id as TabId)}
        />
        <div style={{ width: 1, height: 28, background: "var(--border)" }} />
        <button
          onClick={() => void showSpotlight()}
          title="Spotlight (Ctrl+Shift+Space)"
          style={{ width: 44, height: 44, borderRadius: 12, background: "var(--secondary)", border: "1px solid var(--border)", color: "var(--foreground)", display: "grid", placeItems: "center", cursor: "pointer" }}
        >
          <Sparkles size={18} />
        </button>
        <button
          onClick={() => onModeChange(mode === "chat" ? "overlay" : "chat")}
          title={mode === "chat" ? "Switch to Overlay" : "Switch to Chat"}
          style={{ width: 44, height: 44, borderRadius: 12, background: mode === "overlay" ? "var(--primary)" : "var(--secondary)", color: mode === "overlay" ? "var(--primary-foreground)" : "var(--foreground)", border: "1px solid var(--border)", display: "grid", placeItems: "center", cursor: "pointer" }}
        >
          <Radio size={18} />
        </button>
      </footer>
    </div>
  );
}
