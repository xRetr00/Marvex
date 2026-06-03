export interface StoredMessage {
  role: "user" | "assistant" | "system";
  text: string;
  stages?: unknown;
  directives?: unknown;
  activity?: unknown;
  streaming?: boolean;
  activityStartedAt?: number;
  activityEndedAt?: number;
}

export interface SessionMeta {
  id: string;
  updatedAt: number;
  title: string;
  lastProviderResponseId?: string;
  tokenCount?: number;
}

const INDEX_KEY = "marvex.session.cache.index";
const MSG_PREFIX = "marvex.session.cache.messages.";

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable — cache is optional */
  }
}

export function rememberSession(session: SessionMeta): void {
  const cached = listCachedSessions();
  const existing = cached.find((item) => item.id === session.id);
  const list = cached.filter((item) => item.id !== session.id);
  list.push({ ...existing, ...session });
  writeJson(INDEX_KEY, list.sort((a, b) => b.updatedAt - a.updatedAt));
}

export function loadCachedMessages(id: string): StoredMessage[] {
  return readJson<StoredMessage[]>(MSG_PREFIX + id, []);
}

export function saveCachedMessages(id: string, messages: StoredMessage[]): void {
  writeJson(MSG_PREFIX + id, messages);
  const firstUser = messages.find((m) => m.role === "user");
  rememberSession({
    id,
    title: firstUser ? firstUser.text.slice(0, 48) : "New chat",
    updatedAt: Date.now(),
    tokenCount: estimateSessionTokens(messages),
  });
}

export function listCachedSessions(): SessionMeta[] {
  return readJson<SessionMeta[]>(INDEX_KEY, []).sort((a, b) => b.updatedAt - a.updatedAt);
}

export function renameCachedSession(id: string, title: string): void {
  const cleaned = title.trim().slice(0, 80) || "New chat";
  const next = listCachedSessions().map((item) => item.id === id ? { ...item, title: cleaned, updatedAt: Date.now() } : item);
  writeJson(INDEX_KEY, next.sort((a, b) => b.updatedAt - a.updatedAt));
}

export function deleteCachedSession(id: string): void {
  writeJson(INDEX_KEY, listCachedSessions().filter((item) => item.id !== id));
  try {
    localStorage.removeItem(MSG_PREFIX + id);
  } catch {
    /* optional cache */
  }
}

export function estimateSessionTokens(messages: StoredMessage[]): number {
  const chars = messages.reduce((sum, message) => sum + (message.text?.length ?? 0), 0);
  return Math.max(0, Math.ceil(chars / 4));
}
