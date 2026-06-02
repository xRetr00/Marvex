import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.resetModules();
  vi.clearAllMocks();
});

describe("ChatApp module boundary", () => {
  it("does not let the optional orb renderer break the chat surface import", async () => {
    vi.resetModules();
    vi.doMock("@/components/chat-messages-for-ui/agent-simple-orb", () => {
      throw new Error("orb renderer unavailable");
    });

    await expect(import("./ChatApp")).resolves.toHaveProperty("ChatApp");
  }, 10000);

  it("renders the plus pattern background behind the active chat surface", async () => {
    vi.doMock("@/lib/backendStatus", () => ({
      FAILED_PHASES: new Set<string>(),
      serviceOk: () => true,
      useBackendStatus: () => ({ ready: true, phase: "ready", services: {}, wakeword: "running" }),
    }));
    vi.doMock("@/components/marvex/StartupScreen", async () => {
      const React = await import("react");
      return {
        StartupScreen: ({ onHelloDone }: { onHelloDone?: () => void }) => {
          React.useEffect(() => {
            onHelloDone?.();
          }, [onHelloDone]);
          return <div>startup</div>;
        },
      };
    });
    vi.doMock("@/components/ui/background-plus", () => ({
      BackgroundPlus: ({ plusColor, className }: { plusColor?: string; className?: string }) => (
        <div data-testid="chat-plus-background" data-plus-color={plusColor} className={className} />
      ),
    }));
    vi.doMock("@/lib/tauriBridge", () => ({ listen: vi.fn(async () => vi.fn()) }));
    vi.doMock("@/lib/shellCommands", () => ({
      createChatSession: vi.fn(async () => ({ session: { session_ref: { ref_id: "session-1" }, title: "New chat", updated_at_unix_ms: 0 } })),
      getShellRuntimeConfig: vi.fn(async () => ({ core_base_url: "http://localhost:8765" })),
      listChatSessions: vi.fn(async () => ({ sessions: [] })),
      cancelActiveChatTurn: vi.fn(),
      deleteChatSession: vi.fn(),
      marvexRestart: vi.fn(),
      marvexShutdown: vi.fn(),
      renameChatSession: vi.fn(),
      showOverlay: vi.fn(),
      startBackend: vi.fn(),
      submitChatTurn: vi.fn(),
      submitChatTurnStream: vi.fn(),
      resumeApprovalTurn: vi.fn(),
    }));
    vi.doMock("@/lib/voiceControlClient", () => ({
      fetchVoiceWorkerStatus: vi.fn(),
      listenVoiceWorker: vi.fn(),
      speakVoiceWorker: vi.fn(),
      startVoiceWorker: vi.fn(),
      stopVoiceWorker: vi.fn(),
      transcriptFromStatus: vi.fn(),
    }));

    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);

    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());
    const background = screen.getByTestId("chat-plus-background");
    expect(background).toHaveAttribute("data-plus-color", "#fb3a5d");
    expect(background.className).toContain("pointer-events-none");
    expect(screen.queryByText("http://localhost:8765")).not.toBeInTheDocument();

    await userEvent.click(screen.getByTitle("Sessions"));
    const newChatButton = screen.getByRole("button", { name: "New chat" });
    expect(within(newChatButton).queryByText("New chat")).not.toBeInTheDocument();
  });

  it("keeps approval resume output in the same assistant turn without exposing raw ids", async () => {
    vi.doMock("@/lib/backendStatus", () => ({
      FAILED_PHASES: new Set<string>(),
      serviceOk: () => true,
      useBackendStatus: () => ({ ready: true, phase: "ready", services: {}, wakeword: "disabled" }),
    }));
    vi.doMock("@/components/marvex/StartupScreen", async () => {
      const React = await import("react");
      return {
        StartupScreen: ({ onHelloDone }: { onHelloDone?: () => void }) => {
          React.useEffect(() => {
            onHelloDone?.();
          }, [onHelloDone]);
          return <div>startup</div>;
        },
      };
    });
    vi.doMock("@/components/ui/background-plus", () => ({
      BackgroundPlus: () => <div data-testid="chat-plus-background" />,
    }));
    vi.doMock("@/lib/tauriBridge", () => ({ listen: vi.fn(async () => vi.fn()) }));
    const submitChatTurnStream = vi.fn(async () => ({
      assistant_final_response: {
        text: "Approval required before continuing. approval_request_id=approval-turn-shell-chat-1",
      },
      metadata: {
        approval_request: {
          approval_request_id: "approval-turn-shell-chat-1",
          trace_id: "trace-1",
          turn_id: "turn-1",
        },
      },
    }));
    const resumeApprovalTurn = vi.fn(async () => ({
      assistant_final_response: { text: "Approved. Browser automation completed." },
    }));
    vi.doMock("@/lib/shellCommands", () => ({
      createChatSession: vi.fn(async () => ({ session: { session_ref: { ref_id: "session-1" }, title: "New chat", updated_at_unix_ms: 0 } })),
      getShellRuntimeConfig: vi.fn(async () => ({ core_base_url: "http://localhost:8765" })),
      listChatSessions: vi.fn(async () => ({ sessions: [] })),
      cancelActiveChatTurn: vi.fn(),
      deleteChatSession: vi.fn(),
      marvexRestart: vi.fn(),
      marvexShutdown: vi.fn(),
      renameChatSession: vi.fn(),
      resumeApprovalTurn,
      showOverlay: vi.fn(),
      startBackend: vi.fn(),
      submitChatTurnStream,
    }));
    vi.doMock("@/lib/voiceControlClient", () => ({
      fetchVoiceWorkerStatus: vi.fn(),
      listenVoiceWorker: vi.fn(),
      speakVoiceWorker: vi.fn(),
      startVoiceWorker: vi.fn(),
      stopVoiceWorker: vi.fn(),
      transcriptFromStatus: vi.fn(),
    }));

    const user = userEvent.setup();
    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);

    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());
    await user.type(screen.getByPlaceholderText("Ask anything..."), "Open browser");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText(/Approval required before Marvex continues/i)).toBeInTheDocument();
    expect(screen.queryByText(/approval-turn-shell-chat/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByText(/Browser automation completed/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Browser automation completed/i)).toHaveLength(1);
    expect(resumeApprovalTurn).toHaveBeenCalledWith(expect.objectContaining({ approvalId: "approval-turn-shell-chat-1" }));
  });

  it("uses the composer mic as dictation without submitting a voice turn", async () => {
    vi.doMock("@/lib/backendStatus", () => ({
      FAILED_PHASES: new Set<string>(),
      serviceOk: () => true,
      useBackendStatus: () => ({ ready: true, phase: "ready", services: {}, wakeword: "disabled" }),
    }));
    vi.doMock("@/components/marvex/StartupScreen", async () => {
      const React = await import("react");
      return {
        StartupScreen: ({ onHelloDone }: { onHelloDone?: () => void }) => {
          React.useEffect(() => {
            onHelloDone?.();
          }, [onHelloDone]);
          return <div>startup</div>;
        },
      };
    });
    vi.doMock("@/components/ui/background-plus", () => ({
      BackgroundPlus: () => <div data-testid="chat-plus-background" />,
    }));
    vi.doMock("@/components/chat-messages-for-ui/agent-simple-orb", () => ({
      AgentOrb: () => <div data-testid="agent-orb" />,
    }));
    vi.doMock("@/lib/tauriBridge", () => ({ listen: vi.fn(async () => vi.fn()) }));
    const submitChatTurnStream = vi.fn();
    vi.doMock("@/lib/shellCommands", () => ({
      createChatSession: vi.fn(async () => ({ session: { session_ref: { ref_id: "session-1" }, title: "New chat", updated_at_unix_ms: 0 } })),
      getShellRuntimeConfig: vi.fn(async () => ({ core_base_url: "http://localhost:8765" })),
      listChatSessions: vi.fn(async () => ({ sessions: [] })),
      cancelActiveChatTurn: vi.fn(),
      deleteChatSession: vi.fn(),
      marvexRestart: vi.fn(),
      marvexShutdown: vi.fn(),
      renameChatSession: vi.fn(),
      resumeApprovalTurn: vi.fn(),
      showOverlay: vi.fn(),
      startBackend: vi.fn(),
      submitChatTurnStream,
    }));
    const listenVoiceWorker = vi.fn(async () => ({ recent_events: [] }));
    const speakVoiceWorker = vi.fn(async () => ({}));
    const startVoiceWorker = vi.fn(async () => ({}));
    vi.doMock("@/lib/voiceControlClient", async () => {
      const actual = await vi.importActual<typeof import("@/lib/voiceControlClient")>("@/lib/voiceControlClient");
      return {
        ...actual,
        fetchVoiceWorkerStatus: vi.fn(),
        listenVoiceWorker,
        speakVoiceWorker,
        startVoiceWorker,
        stopVoiceWorker: vi.fn(),
        transcriptFromStatus: vi.fn(() => ({ text: "hello by voice", eventId: "voice-event-1" })),
      };
    });

    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);
    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));

    await waitFor(() => expect(listenVoiceWorker).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByPlaceholderText("Ask anything...")).toHaveValue("hello by voice"));
    expect(submitChatTurnStream).not.toHaveBeenCalled();
    expect(speakVoiceWorker).not.toHaveBeenCalled();
    expect(startVoiceWorker).not.toHaveBeenCalled();
  });
});
