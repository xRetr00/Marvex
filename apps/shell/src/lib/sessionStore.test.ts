import { beforeEach, describe, expect, it } from "vitest";
import { loadCachedMessages, saveCachedMessages, rememberSession, listCachedSessions } from "./sessionStore";

beforeEach(() => localStorage.clear());

describe("sessionStore", () => {
  it("round-trips cached messages for a backend-owned session", () => {
    saveCachedMessages("session-backend-1", [{ role: "user", text: "hi" }]);
    expect(loadCachedMessages("session-backend-1")).toEqual([{ role: "user", text: "hi" }]);
  });

  it("remembers backend sessions without minting ids locally", () => {
    rememberSession({ id: "session-backend-1", title: "Backend", updatedAt: 100 });
    const ids = listCachedSessions().map((s) => s.id);
    expect(ids).toEqual(["session-backend-1"]);
  });
});
