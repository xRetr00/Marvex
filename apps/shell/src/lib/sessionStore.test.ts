import { beforeEach, describe, expect, it } from "vitest";
import { getActiveSessionId, newSession, loadMessages, saveMessages, listSessions } from "./sessionStore";

beforeEach(() => localStorage.clear());

describe("sessionStore", () => {
  it("creates and persists a stable active session id", () => {
    const id = getActiveSessionId();
    expect(id).toMatch(/^session-/);
    expect(getActiveSessionId()).toBe(id); // stable across calls
  });

  it("round-trips messages for a session", () => {
    const id = getActiveSessionId();
    saveMessages(id, [{ role: "user", text: "hi" }]);
    expect(loadMessages(id)).toEqual([{ role: "user", text: "hi" }]);
  });

  it("newSession switches the active id and lists prior sessions", () => {
    const first = getActiveSessionId();
    saveMessages(first, [{ role: "user", text: "one" }]);
    const second = newSession();
    expect(second).not.toBe(first);
    expect(getActiveSessionId()).toBe(second);
    const ids = listSessions().map((s) => s.id);
    expect(ids).toContain(first);
  });
});
