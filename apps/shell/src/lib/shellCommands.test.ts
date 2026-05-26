import { describe, expect, it, vi } from "vitest";
import { controlPlaneEntryUrl, createChatSession, listChatSessions, submitChatTurn } from "./shellCommands";
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
      },
      previousResponseId: undefined
    });
  });

  it("passes the prior provider response id separately from metadata", async () => {
    await submitChatTurn("follow up", { session_id: "session-1" }, "resp-previous-001");

    expect(mockedInvoke).toHaveBeenCalledWith("submit_chat_turn", {
      text: "follow up",
      metadata: { session_id: "session-1" },
      previousResponseId: "resp-previous-001"
    });
  });

  it("uses backend-owned chat session commands", async () => {
    await createChatSession("Planning");
    await listChatSessions();

    expect(mockedInvoke).toHaveBeenCalledWith("create_chat_session", { title: "Planning" });
    expect(mockedInvoke).toHaveBeenCalledWith("list_chat_sessions");
  });

  it("requests a Control Plane entry URL instead of a browser token", async () => {
    await controlPlaneEntryUrl();

    expect(mockedInvoke).toHaveBeenCalledWith("control_plane_entry_url");
  });
});
