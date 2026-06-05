import { describe, expect, it, vi } from "vitest";
import { cancelProviderResponse, controlPlaneEntryUrl, createChatSession, deleteProviderResponse, listChatSessions, resumeApprovalTurn, submitChatTurn, submitChatTurnStream } from "./shellCommands";
import { invoke, listen } from "./tauriBridge";

vi.mock("./tauriBridge", () => ({
  invoke: vi.fn(async () => ({ ok: true })),
  listen: vi.fn(async () => vi.fn()),
}));

const mockedInvoke = vi.mocked(invoke);
const mockedListen = vi.mocked(listen);

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

  it("passes approval resume fields through the bridge", async () => {
    await resumeApprovalTurn({
      text: "delete this file",
      traceId: "trace-1",
      turnId: "turn-1",
      approvalId: "approval-turn-1",
      decision: "approve",
    });

    expect(mockedInvoke).toHaveBeenCalledWith("resume_approval_turn", {
      text: "delete this file",
      traceId: "trace-1",
      turnId: "turn-1",
      approvalId: "approval-turn-1",
      decision: "approve",
    });
  });

  it("requests a Control Plane entry URL instead of a browser token", async () => {
    await controlPlaneEntryUrl();

    expect(mockedInvoke).toHaveBeenCalledWith("control_plane_entry_url");
  });

  it("passes provider response cancel and delete through the shell bridge", async () => {
    await cancelProviderResponse("resp-cancel");
    await deleteProviderResponse("resp-delete");

    expect(mockedInvoke).toHaveBeenCalledWith("cancel_provider_response", { responseId: "resp-cancel" });
    expect(mockedInvoke).toHaveBeenCalledWith("delete_provider_response", { responseId: "resp-delete" });
  });

  it("resolves a streaming turn from its terminal final event even if invoke is still pending", async () => {
    let streamHandler: ((event: { payload: unknown }) => void) | undefined;
    mockedListen.mockImplementationOnce(async (_event, handler) => {
      streamHandler = handler as (event: { payload: unknown }) => void;
      return () => undefined;
    });
    mockedInvoke.mockImplementationOnce(() => new Promise(() => undefined));
    const result = { assistant_final_response: { text: "Voice reply" } };

    const pending = submitChatTurnStream("hello", { session_id: "session-1" }, undefined, () => undefined);
    await vi.waitFor(() => expect(streamHandler).toBeDefined());
    const invokeArgs = mockedInvoke.mock.calls.at(-1)?.[1] as { requestId?: string } | undefined;
    streamHandler?.({ payload: { request_id: invokeArgs?.requestId, turn_id: "turn-1", event: { type: "final", result } } });

    await expect(pending).resolves.toEqual(result);
  });

  it("forwards live provider response ids from streaming turns", async () => {
    let streamHandler: ((event: { payload: unknown }) => void) | undefined;
    mockedListen.mockImplementationOnce(async (_event, handler) => {
      streamHandler = handler as (event: { payload: unknown }) => void;
      return () => undefined;
    });
    mockedInvoke.mockImplementationOnce(() => new Promise(() => undefined));
    const onResponse = vi.fn();
    const result = { assistant_final_response: { text: "Done" } };

    const pending = submitChatTurnStream(
      "hello",
      { session_id: "session-1" },
      undefined,
      { onDelta: () => undefined, onResponse },
    );
    await vi.waitFor(() => expect(streamHandler).toBeDefined());
    const invokeArgs = mockedInvoke.mock.calls.at(-1)?.[1] as { requestId?: string } | undefined;
    streamHandler?.({ payload: { request_id: invokeArgs?.requestId, turn_id: "turn-1", event: { type: "response", response_id: "resp-live" } } });
    streamHandler?.({ payload: { request_id: invokeArgs?.requestId, turn_id: "turn-1", event: { type: "final", result } } });

    await expect(pending).resolves.toEqual(result);
    expect(onResponse).toHaveBeenCalledWith("resp-live");
  });

  it("ignores terminal events emitted for another streaming turn", async () => {
    let streamHandler: ((event: { payload: unknown }) => void) | undefined;
    mockedListen.mockImplementationOnce(async (_event, handler) => {
      streamHandler = handler as (event: { payload: unknown }) => void;
      return () => undefined;
    });
    mockedInvoke.mockImplementationOnce(() => new Promise(() => undefined));
    const result = { assistant_final_response: { text: "Correct reply" } };

    const pending = submitChatTurnStream("hello", { session_id: "session-1" }, undefined, () => undefined);
    await vi.waitFor(() => expect(streamHandler).toBeDefined());
    const invokeArgs = mockedInvoke.mock.calls.at(-1)?.[1] as { requestId?: string } | undefined;
    expect(invokeArgs?.requestId).toBeTruthy();

    streamHandler?.({
      payload: {
        request_id: "another-request",
        turn_id: "another-turn",
        event: { type: "error", message: "Chat turn stopped.", reason: "user_cancelled" },
      },
    });
    streamHandler?.({
      payload: {
        request_id: invokeArgs?.requestId,
        turn_id: "turn-1",
        event: { type: "final", result },
      },
    });

    await expect(pending).resolves.toEqual(result);
  });
});
