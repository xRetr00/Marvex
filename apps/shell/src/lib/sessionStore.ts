export interface StoredMessage {
  role: "user" | "assistant" | "system";
  text: string;
  stages?: unknown;
  directives?: unknown;
}

export interface SessionMeta {
  id: string;
  createdAt: number;
  updatedAt: number;
  title: string;
}

const ACTIVE_KEY = "marvex.session.active";
const INDEX_KEY = "marvex.session.index";
const MSG_PREFIX = "marvex.session.messages.";

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
    /* storage unavailable — degrade to in-memory only for this session */
  }
}

function makeId(): string {
  const rand = Math.random().toString(36).slice(2, 10);
  return `session-${Date.now()}-${rand}`;
}

function index(): SessionMeta[] {
  return readJson<SessionMeta[]>(INDEX_KEY, []);
}

function upsertMeta(id: string, patch: Partial<SessionMeta>): void {
  const list = index();
  const now = Date.now();
  const existing = list.find((m) => m.id === id);
  if (existing) {
    Object.assign(existing, patch, { updatedAt: now });
  } else {
    list.push({ id, createdAt: now, updatedAt: now, title: "New chat", ...patch });
  }
  writeJson(INDEX_KEY, list);
}

export function getActiveSessionId(): string {
  let id = localStorage.getItem(ACTIVE_KEY);
  if (!id) {
    id = makeId();
    localStorage.setItem(ACTIVE_KEY, id);
    upsertMeta(id, { title: "New chat" });
  }
  return id;
}

export function newSession(): string {
  const id = makeId();
  localStorage.setItem(ACTIVE_KEY, id);
  upsertMeta(id, { title: "New chat" });
  return id;
}

export function setActiveSession(id: string): void {
  localStorage.setItem(ACTIVE_KEY, id);
}

export function loadMessages(id: string): StoredMessage[] {
  return readJson<StoredMessage[]>(MSG_PREFIX + id, []);
}

export function saveMessages(id: string, messages: StoredMessage[]): void {
  writeJson(MSG_PREFIX + id, messages);
  const firstUser = messages.find((m) => m.role === "user");
  upsertMeta(id, firstUser ? { title: firstUser.text.slice(0, 48) } : {});
}

export function listSessions(): SessionMeta[] {
  return index().sort((a, b) => b.updatedAt - a.updatedAt);
}
