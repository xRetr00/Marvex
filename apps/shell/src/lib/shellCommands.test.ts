import { describe, expect, it, vi } from "vitest";
import { submitChatTurn } from "./shellCommands";
import { invoke } from "./tauriBridge";

vi.mock("./tauriBridge", () => ({
  invoke: vi.fn(async () => ({ ok: true }))
}));

const mockedInvoke = vi.mocked(invoke);

describe("shell command bridge", () => {
  it("passes selected runtime metadata into chat turns", async () => {
    await submitChatTurn("hello", {
      agent_profile_id: "agent.deep_search",
      persona_profile_id: "persona.marvex.female",
      selected_voice_id: "af_heart"
    });

    expect(mockedInvoke).toHaveBeenCalledWith("submit_chat_turn", {
      text: "hello",
      metadata: {
        agent_profile_id: "agent.deep_search",
        persona_profile_id: "persona.marvex.female",
        selected_voice_id: "af_heart"
      }
    });
  });
});
