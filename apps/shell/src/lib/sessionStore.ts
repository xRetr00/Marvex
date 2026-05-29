export interface StoredMessage {
  role: "user" | "assistant" | "system";
  text: string;
  stages?: unknown;
  directives?: unknown;
}

export interface SessionMeta {
  id: string;
  updatedAt: number;
  title: string;
  lastProviderResponseId?: string;
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
  // Fix #4: only derive title from the first user message when the session
  // does not already have an explicit title set by the backend / rememberSession.
  const existing = listCachedSessions().find((item) => item.id === id);
  const firstUser = messages.find((m) => m.role === "user");
  const derivedTitle = firstUser ? firstUser.text.slice(0, 48) : "New chat";
  rememberSession({
    id,
    // Preserve an existing non-default title rather than overwriting it.
    title: existing?.title && existing.title !== "New chat" ? existing.title : derivedTitle,
    updatedAt: Date.now(),
  });
}

export function listCachedSessions(): SessionMeta[] {
  return readJson<SessionMeta[]>(INDEX_KEY, []).sort((a, b) => b.updatedAt - a.updatedAt);
}
