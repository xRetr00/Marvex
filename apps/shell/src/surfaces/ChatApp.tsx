import { useEffect, useMemo, useState } from "react";
import { MessageSquare, Mic, Radio, Search, Send, ShieldCheck } from "lucide-react";
import { listen } from "../lib/tauriBridge";
import { finalTextFromTurnResult } from "../lib/localTurn";
import { getShellRuntimeConfig, showSpotlight, submitChatTurn, type ShellRuntimeConfig } from "../lib/shellCommands";
import { idleAssistantState, normalizeAssistantState, statusLabel, type AssistantStateEvent } from "../lib/assistantState";

type ChatMessage = { role: "user" | "assistant" | "system"; text: string };

export function ChatApp() {
  const [config, setConfig] = useState<ShellRuntimeConfig | null>(null);
  const [state, setState] = useState<AssistantStateEvent>(idleAssistantState);
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "system", text: "Marvex Shell is supervising the local backend." }]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const statusText = useMemo(() => statusLabel(state.status), [state.status]);

  useEffect(() => {
    void getShellRuntimeConfig().then(setConfig).catch(() => setConfig(null));
    let cleanup: VoidFunction | undefined;
    void listen("assistant-state", (event) => {
      try {
        setState(normalizeAssistantState(event.payload));
      } catch {
        setState(idleAssistantState);
      }
    }).then((unlisten) => { cleanup = unlisten; });
    return () => cleanup?.();
  }, []);

  async function send() {
    const text = input.trim();
    if (!text || pending) return;
    setInput("");
    setPending(true);
    setMessages((current) => [...current, { role: "user", text }]);
    try {
      const result = await submitChatTurn(text);
      setMessages((current) => [...current, { role: "assistant", text: finalTextFromTurnResult(result) }]);
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", text: error instanceof Error ? error.message : "Local Core request failed." }]);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="app-shell">
      <aside className="rail">
        <div className="brand">Marvex</div>
        <button className="rail-button active" title="Chat"><MessageSquare size={18} /></button>
        <button className="rail-button" title="Spotlight" onClick={() => void showSpotlight()}><Search size={18} /></button>
        <button className="rail-button" title="Approvals"><ShieldCheck size={18} /></button>
      </aside>
      <section className="chat-pane">
        <header className="topbar">
          <div>
            <h1>Assistant Shell</h1>
            <p>{config ? `${config.core_base_url} · token in memory only` : "Connecting to supervised loopback services"}</p>
          </div>
          <div className="state-chip"><Radio size={16} /> {statusText}</div>
        </header>
        <div className="messages">
          {messages.map((message, index) => <article className={`message ${message.role}`} key={`${message.role}-${index}`}>{message.text}</article>)}
        </div>
        <form className="composer" onSubmit={(event) => { event.preventDefault(); void send(); }}>
          <button type="button" title="Microphone routed through VoiceWorker"><Mic size={18} /></button>
          <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask Marvex..." />
          <button type="submit" disabled={pending || !input.trim()}><Send size={18} /> Send</button>
        </form>
      </section>
    </main>
  );
}
