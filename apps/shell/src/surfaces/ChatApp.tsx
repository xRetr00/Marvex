import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { MessageSquare, Search, Settings, Package, Mic, MicOff, Radio } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { listen } from "@/lib/tauriBridge";
import { finalTextFromTurnResult, stagesFromTurnResult, type TurnStage } from "@/lib/localTurn";
import { getShellRuntimeConfig, showSpotlight, submitChatTurn, type ShellRuntimeConfig } from "@/lib/shellCommands";
import { idleAssistantState, normalizeAssistantState, statusLabel, type AssistantStateEvent, type AssistantStatusKind } from "@/lib/assistantState";
import { fetchDeps, installDep, type Dep } from "@/lib/depsClient";
import type { AppMode } from "@/lib/modeStore";

import { LimelightNav } from "@/components/dock";
import { Loader } from "@/components/loader";
import { Badge } from "@/components/ui/badge";
import { AppleHelloEnglishEffect } from "@/components/apple-hello-effect";
import { Typewriter } from "@/components/typewriter";
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

type ChatMessage = { role: "user" | "assistant" | "system"; text: string; stages?: TurnStage[] };
type TabId = "chat" | "spotlight" | "settings" | "deps";

interface ChatAppProps {
  mode: AppMode;
  onModeChange: (mode: AppMode) => void;
}

const TAB_TITLES: Record<TabId, string> = {
  chat: "Assistant Chat",
  spotlight: "Spotlight",
  settings: "Settings",
  deps: "Dependencies",
};

// Feature gating: map feature keys to UI labels
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
    { role: "system", text: "Marvex Shell is ready. How can I help?" },
  ]);
  const [pending, setPending] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const [showHello, setShowHello] = useState(true);
  const [micActive, setMicActive] = useState(false);

  // Deps state
  const [deps, setDeps] = useState<Dep[]>([]);
  const [features, setFeatures] = useState<Record<string, boolean>>({});
  const [installingDep, setInstallingDep] = useState<string | null>(null);
  const [depProgress, setDepProgress] = useState<Record<string, number>>({});

  // Settings state
  const [selectedVoice, setSelectedVoice] = useState<string>("kokoro-default");

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
    void fetchDeps()
      .then((data) => { setDeps(data.deps); setFeatures(data.features); })
      .catch(() => undefined);
  }, []);

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
      setMessages((prev) => [...prev, { role: "assistant", text: finalTextFromTurnResult(result), stages: stagesFromTurnResult(result) }]);
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
    { id: "spotlight", icon: <Search />, label: "Spotlight", onClick: () => { setActiveTab("spotlight"); void showSpotlight(); } },
    { id: "settings", icon: <Settings />, label: "Settings", onClick: () => setActiveTab("settings") },
    { id: "deps", icon: <Package />, label: "Deps", onClick: () => setActiveTab("deps") },
  ], []);
  const activeNavIndex = navItems.findIndex((n) => n.id === activeTab);

  const orbState = agentStateFromStatus(state.status);

  return (
    <div className="marvex-shell" style={{ display: "grid", gridTemplateColumns: "72px 1fr", minHeight: "100vh" }}>
      {/* Rail */}
      <aside style={{ background: "#0a1a20", color: "#f7fbfb", padding: "16px 0", display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
        <div style={{ marginBottom: 8, padding: "4px 8px" }}>
          <img src="/assets/Marvex_Logo-Round.png" alt="Marvex" style={{ width: 36, height: 36, borderRadius: "50%", objectFit: "cover" }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
        </div>
        <LimelightNav
          items={navItems}
          defaultActiveIndex={activeNavIndex}
          onTabChange={(idx) => setActiveTab(navItems[idx].id as TabId)}
          className="flex-col h-auto border-0 bg-transparent px-0 gap-1"
          iconContainerClassName="p-2"
        />
        {/* Mode toggle */}
        <div style={{ marginTop: "auto", padding: "0 8px 16px" }}>
          <button
            onClick={() => onModeChange(mode === "chat" ? "overlay" : "chat")}
            title={mode === "chat" ? "Switch to Overlay" : "Switch to Chat"}
            style={{ width: 40, height: 40, borderRadius: 8, background: mode === "overlay" ? "#1f6f78" : "transparent", border: "1px solid rgba(255,255,255,.16)", color: "#f7fbfb", display: "grid", placeItems: "center", cursor: "pointer" }}
          >
            <Radio size={16} />
          </button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0, background: "var(--background)", color: "var(--foreground)" }}>
        {/* Topbar */}
        <header style={{ minHeight: 64, padding: "12px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", background: "var(--card)" }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "var(--foreground)" }}>
              {TAB_TITLES[activeTab]}
            </h1>
            <p style={{ margin: "2px 0 0", color: "var(--muted-foreground)", fontSize: 12 }}>
              {config ? `${config.core_base_url}` : "Connecting..."}
            </p>
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
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <AnimatePresence mode="wait">
            {activeTab === "chat" && (
              <motion.div key="chat" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                {/* Hello splash */}
                <AnimatePresence>
                  {showHello && (
                    <motion.div exit={{ opacity: 0, scale: 0.8 }} className="absolute inset-0 flex items-center justify-center bg-background z-10 pointer-events-none">
                      <AppleHelloEnglishEffect className="text-primary h-20" onAnimationComplete={() => setTimeout(() => setShowHello(false), 400)} />
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Messages */}
                <div style={{ flex: 1, overflow: "auto", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 8 }}>
                  {messages.map((msg, idx) => (
                    <Message key={`${msg.role}-${idx}`} from={msg.role === "user" ? "user" : "assistant"}>
                      {msg.role === "assistant" ? (
                        <MessageContent variant="flat" className="w-full max-w-[88%]">
                          <RichMessage text={msg.text} stages={msg.stages} />
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
                  <div style={{ padding: "0 20px 8px", textAlign: "center" }}>
                    <Typewriter
                      text={["How can I help you today?", "Ask me anything...", "What shall we work on?"]}
                      speed={60} loop className="text-gray-400 text-sm"
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
                      style={{ width: 40, height: 40, borderRadius: 8, border: "1px solid var(--border)", background: micActive ? "var(--primary)" : "var(--secondary)", color: micActive ? "var(--primary-foreground)" : "var(--foreground)", display: "grid", placeItems: "center", cursor: sttAvailable ? "pointer" : "not-allowed", opacity: sttAvailable ? 1 : 0.4 }}
                    >
                      {micActive ? <MicOff size={16} /> : <Mic size={16} />}
                    </button>
                    <div style={{ flex: 1 }}>
                      <ChatInput
                        placeholder="Ask Marvex..."
                        disabled={pending}
                        onSubmit={send}
                        textColor="#eef6f7"
                        backgroundOpacity={0.08}
                      />
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "settings" && (
              <motion.div key="settings" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ flex: 1, overflow: "auto", padding: 20 }}>
                <div style={{ maxWidth: 600, display: "flex", flexDirection: "column", gap: 20 }}>
                  {/* Voice selector */}
                  <section style={{ background: "var(--card)", borderRadius: 12, padding: 20, border: "1px solid var(--border)" }}>
                    <h2 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600 }}>TTS Voice</h2>
                    {!ttsAvailable && (
                      <div style={{ padding: "8px 12px", background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.35)", borderRadius: 8, marginBottom: 12, color: "#fbbf24", fontSize: 12 }}>
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

                  {/* Assistant status */}
                  <section style={{ background: "var(--card)", borderRadius: 12, padding: 20, border: "1px solid var(--border)" }}>
                    <h2 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600 }}>Assistant Status</h2>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Status status={state.status === "idle" ? "online" : "degraded"}>
                        <StatusIndicator />
                        <StatusLabel>{state.status === "idle" ? "Online" : statusText}</StatusLabel>
                      </Status>
                      {state.detail && <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>{state.detail}</span>}
                    </div>
                  </section>

                  {/* System monitor */}
                  <section>
                    <h2 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600 }}>System Monitor</h2>
                    <SystemMonitor />
                  </section>
                </div>
              </motion.div>
            )}

            {activeTab === "deps" && (
              <motion.div key="deps" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ flex: 1, overflow: "auto", padding: 20 }}>
                <div style={{ maxWidth: 680, display: "flex", flexDirection: "column", gap: 16 }}>
                  {/* Feature status */}
                  {Object.keys(features).length > 0 && (
                    <section style={{ background: "var(--card)", borderRadius: 12, padding: 16, border: "1px solid var(--border)" }}>
                      <h2 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 600, color: "var(--muted-foreground)" }}>Feature Status</h2>
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
                  <section style={{ background: "var(--card)", borderRadius: 12, border: "1px solid var(--border)", overflow: "hidden" }}>
                    <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)", fontWeight: 600, fontSize: 14 }}>
                      Models & Dependencies
                    </div>
                    {deps.length === 0 ? (
                      <div style={{ padding: 24, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>
                        <Loader variant="circular" size="md" />
                        <p style={{ marginTop: 8 }}>Loading deps...</p>
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column" }}>
                        {deps.map((dep) => {
                          const isInstalling = installingDep === dep.id;
                          const progress = depProgress[dep.id] ?? 0;
                          return (
                            <div key={dep.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontSize: 13, fontWeight: 500 }}>{dep.label}</div>
                                <div style={{ fontSize: 11, color: "var(--muted-foreground)" }}>{dep.group}</div>
                                {isInstalling && <AnimatedProgressBar value={progress} color="#0f5f6a" className="mt-2" />}
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

            {activeTab === "spotlight" && (
              <motion.div key="spotlight" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
                <div style={{ textAlign: "center", color: "var(--muted-foreground)" }}>
                  <Search size={32} style={{ margin: "0 auto 12px" }} />
                  <p>Spotlight opened in overlay window</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
