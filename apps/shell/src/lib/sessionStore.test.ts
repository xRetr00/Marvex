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

  it("preserves the last provider response id when message saves refresh metadata", () => {
    rememberSession({
      id: "session-backend-1",
      title: "Backend",
      updatedAt: 100,
      lastProviderResponseId: "resp-001",
      providerUsage: { inputTokens: 10, outputTokens: 2, totalTokens: 12, cachedInputTokens: 1, reasoningTokens: 0 },
    });

    saveCachedMessages("session-backend-1", [{ role: "user", text: "next" }]);

    expect(listCachedSessions()[0]).toMatchObject({
      id: "session-backend-1",
      lastProviderResponseId: "resp-001",
      providerUsage: { inputTokens: 10, outputTokens: 2, totalTokens: 12, cachedInputTokens: 1, reasoningTokens: 0 },
    });
  });
});
