import { describe, expect, it, vi } from "vitest";

describe("ChatApp module boundary", () => {
  it("does not let the optional orb renderer break the chat surface import", async () => {
    vi.resetModules();
    vi.doMock("@/components/chat-messages-for-ui/agent-simple-orb", () => {
      throw new Error("orb renderer unavailable");
    });

    await expect(import("./ChatApp")).resolves.toHaveProperty("ChatApp");
  });
});
