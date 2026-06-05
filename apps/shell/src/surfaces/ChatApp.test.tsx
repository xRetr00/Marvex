import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LISTENING_CUES } from "@/lib/voiceFillers";

afterEach(() => {
  cleanup();
  vi.resetModules();
  vi.clearAllMocks();
});

describe("ChatApp module boundary", () => {
  it("shows the central app version in the chat header", async () => {
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
      BackgroundPlus: () => <div data-testid="chat-plus-background" />,
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
      resumeApprovalTurn: vi.fn(),
      showOverlay: vi.fn(),
      startBackend: vi.fn(),
      submitChatTurnStream: vi.fn(),
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
    expect(screen.getByLabelText("Marvex version")).toHaveTextContent("v0.3.0");
  });

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

  it("clears stale working state after final response and accumulates session usage", async () => {
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
      Orb: () => <div data-testid="agent-orb" />,
    }));
    let assistantStateHandler: ((event: { payload: unknown }) => void) | undefined;
    vi.doMock("@/lib/tauriBridge", () => ({
      listen: vi.fn(async (channel: string, handler: (event: { payload: unknown }) => void) => {
        if (channel === "assistant-state") assistantStateHandler = handler;
        return vi.fn();
      }),
    }));
    let turn = 0;
    const turnResolvers: Array<() => void> = [];
    const submitChatTurnStream = vi.fn(async (_text, _metadata, _previousResponseId, handlers) => {
      turn += 1;
      handlers.onDelta?.(`Answer ${turn}`);
      await new Promise<void>((resolve) => {
        turnResolvers.push(resolve);
      });
      return {
        assistant_final_response: { text: `Answer ${turn}` },
        metadata: {
          provider_usage: {
            input_tokens: turn * 100,
            output_tokens: turn * 10,
            total_tokens: turn * 110,
          },
        },
      };
    });
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

    await userEvent.type(screen.getByPlaceholderText("Ask anything..."), "First");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(submitChatTurnStream).toHaveBeenCalledTimes(1));
    act(() => {
      assistantStateHandler?.({
        payload: {
          schema_version: "1",
          ts: new Date().toISOString(),
          status: "thinking",
          detail: null,
          audio_level: 0,
          raw_audio_persisted: false,
        },
      });
    });
    expect(screen.getByText("Thinking")).toBeInTheDocument();

    await act(async () => {
      turnResolvers.shift()?.();
    });
    expect(await screen.findByText("Answer 1")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Ready")).toBeInTheDocument());
    expect(screen.getByLabelText("Input tokens: 100")).toHaveTextContent("100");

    act(() => {
      assistantStateHandler?.({
        payload: {
          schema_version: "1",
          ts: new Date().toISOString(),
          status: "working",
          detail: null,
          audio_level: 0,
          raw_audio_persisted: false,
        },
      });
    });
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.queryByText("Thinking")).not.toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText("Ask anything..."), "Second");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(submitChatTurnStream).toHaveBeenCalledTimes(2));
    await act(async () => {
      turnResolvers.shift()?.();
    });
    expect(await screen.findByText("Answer 2")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Input tokens: 300")).toHaveTextContent("300"));
    expect(screen.getByLabelText("Output tokens: 30")).toHaveTextContent("30");
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
      Orb: () => <div data-testid="agent-orb" />,
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

  it("routes a queued composer dictation transcript into the input instead of submitting it", async () => {
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
      BackgroundPlus: () => <div data-testid="chat-plus-background" />,
    }));
    vi.doMock("@/components/chat-messages-for-ui/agent-simple-orb", () => ({
      Orb: () => <div data-testid="agent-orb" />,
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
    const listenVoiceWorker = vi.fn(async () => ({
      recent_events: [{ event_type: "vad_speech_started", event_id: "queued-1", summary: { manual_listen_queued: true } }],
    }));
    const fetchVoiceWorkerStatus = vi.fn(async () => ({
      recent_events: [{ event_type: "transcription_completed", event_id: "voice-event-queued", summary: { normalized_transcript_text: "queued dictation text" } }],
    }));
    vi.doMock("@/lib/voiceControlClient", async () => {
      const actual = await vi.importActual<typeof import("@/lib/voiceControlClient")>("@/lib/voiceControlClient");
      return {
        ...actual,
        fetchVoiceWorkerStatus,
        listenVoiceWorker,
        speakVoiceWorker: vi.fn(),
        startVoiceWorker: vi.fn(),
        stopVoiceWorker: vi.fn(),
      };
    });

    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);
    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));

    await waitFor(() => expect(listenVoiceWorker).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByPlaceholderText("Ask anything...")).toHaveValue("queued dictation text"), { timeout: 3000 });
    expect(submitChatTurnStream).not.toHaveBeenCalled();
  });

  it("places manual voice mode beside the composer and only speaks one start cue", async () => {
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
      BackgroundPlus: () => <div data-testid="chat-plus-background" />,
    }));
    vi.doMock("@/components/chat-messages-for-ui/agent-simple-orb", () => ({
      Orb: () => <div data-testid="agent-orb" />,
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
      resumeApprovalTurn: vi.fn(),
      showOverlay: vi.fn(),
      startBackend: vi.fn(),
      submitChatTurnStream: vi.fn(),
    }));
    const speakVoiceWorker = vi.fn(async () => ({ recent_events: [] }));
    const listenVoiceWorker = vi.fn(async () => ({
      recent_events: [{ event_type: "vad_speech_started", event_id: "queued-voice", summary: { manual_listen_queued: true } }],
    }));
    const startVoiceWorker = vi.fn(async () => ({ recent_events: [] }));
    vi.doMock("@/lib/voiceControlClient", async () => {
      const actual = await vi.importActual<typeof import("@/lib/voiceControlClient")>("@/lib/voiceControlClient");
      return {
        ...actual,
        fetchVoiceWorkerStatus: vi.fn(async () => ({ recent_events: [] })),
        listenVoiceWorker,
        speakVoiceWorker,
        startVoiceWorker,
        stopVoiceWorker: vi.fn(),
      };
    });

    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);
    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Start voice mode" }));

    await waitFor(() => expect(startVoiceWorker).toHaveBeenCalled());
    await waitFor(() => expect(listenVoiceWorker).toHaveBeenCalled());
    expect(speakVoiceWorker).toHaveBeenCalledTimes(1);
    const cueText = (speakVoiceWorker.mock.calls[0] as unknown[])[0];
    expect(LISTENING_CUES as readonly string[]).toContain(cueText);
    expect(screen.getByRole("button", { name: "Stop voice mode" })).toBeInTheDocument();
  });

  it("submits a manual voice transcript, renders the reply, and speaks it", async () => {
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
      BackgroundPlus: () => <div data-testid="chat-plus-background" />,
    }));
    vi.doMock("@/components/chat-messages-for-ui/agent-simple-orb", () => ({
      Orb: () => <div data-testid="agent-orb" />,
    }));
    vi.doMock("@/lib/tauriBridge", () => ({ listen: vi.fn(async () => vi.fn()) }));
    const submitChatTurnStream = vi.fn(async (_text, _metadata, _previousResponseId, handlers) => {
      handlers.onStatus?.({ type: "status", status: "thinking" });
      handlers.onDelta("Voice reply");
      return { assistant_final_response: { text: "Voice reply", safe_for_speech: true } };
    });
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
    const listenVoiceWorker = vi.fn(async () => ({
      recent_events: [{ event_type: "transcription_completed", event_id: "voice-ok", summary: { normalized_transcript_text: "hello marvex" } }],
    }));
    const speakVoiceWorker = vi.fn(async () => ({ recent_events: [] }));
    vi.doMock("@/lib/voiceControlClient", async () => {
      const actual = await vi.importActual<typeof import("@/lib/voiceControlClient")>("@/lib/voiceControlClient");
      return {
        ...actual,
        fetchVoiceWorkerStatus: vi.fn(async () => ({ recent_events: [] })),
        listenVoiceWorker,
        speakVoiceWorker,
        startVoiceWorker: vi.fn(async () => ({ recent_events: [] })),
        stopVoiceWorker: vi.fn(),
      };
    });

    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);
    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Start voice mode" }));

    expect(await screen.findByText("hello marvex")).toBeInTheDocument();
    expect(await screen.findByText("Voice reply")).toBeInTheDocument();
    await waitFor(() => expect(speakVoiceWorker).toHaveBeenCalledWith("Voice reply", { bargeIn: true }));
  });

  it("suppresses duplicate voice submissions while the first voice turn is still pending", async () => {
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
      BackgroundPlus: () => <div data-testid="chat-plus-background" />,
    }));
    vi.doMock("@/components/chat-messages-for-ui/agent-simple-orb", () => ({
      Orb: () => <div data-testid="agent-orb" />,
    }));
    vi.doMock("@/lib/tauriBridge", () => ({ listen: vi.fn(async () => vi.fn()) }));
    let resolveTurn: (value: unknown) => void = () => undefined;
    const submitChatTurnStream = vi.fn(() => new Promise((resolve) => { resolveTurn = resolve; }));
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
    const listenVoiceWorker = vi.fn(async () => ({
      recent_events: [{ event_type: "transcription_completed", event_id: "voice-1", summary: { normalized_transcript_text: "first voice" } }],
    }));
    const fetchVoiceWorkerStatus = vi.fn(async () => ({
      recent_events: [{ event_type: "transcription_completed", event_id: "voice-2", summary: { normalized_transcript_text: "second voice" } }],
    }));
    vi.doMock("@/lib/voiceControlClient", async () => {
      const actual = await vi.importActual<typeof import("@/lib/voiceControlClient")>("@/lib/voiceControlClient");
      return {
        ...actual,
        fetchVoiceWorkerStatus,
        listenVoiceWorker,
        speakVoiceWorker: vi.fn(async () => ({ recent_events: [] })),
        startVoiceWorker: vi.fn(async () => ({ recent_events: [] })),
        stopVoiceWorker: vi.fn(),
      };
    });

    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);
    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Start voice mode" }));
    await waitFor(() => expect(submitChatTurnStream).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(fetchVoiceWorkerStatus).toHaveBeenCalled(), { timeout: 2500 });
    expect(submitChatTurnStream).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveTurn({ assistant_final_response: { text: "done", safe_for_speech: true } });
    });
  });

  it("stops manual voice mode and ignores late queued listen results", async () => {
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
      BackgroundPlus: () => <div data-testid="chat-plus-background" />,
    }));
    vi.doMock("@/components/chat-messages-for-ui/agent-simple-orb", () => ({
      Orb: () => <div data-testid="agent-orb" />,
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
      resumeApprovalTurn: vi.fn(),
      showOverlay: vi.fn(),
      startBackend: vi.fn(),
      submitChatTurnStream: vi.fn(),
    }));
    let resolveListen: (status: unknown) => void = () => undefined;
    const listenVoiceWorker = vi.fn(() => new Promise((resolve) => { resolveListen = resolve; }));
    const speakVoiceWorker = vi.fn(async () => ({ recent_events: [] }));
    vi.doMock("@/lib/voiceControlClient", async () => {
      const actual = await vi.importActual<typeof import("@/lib/voiceControlClient")>("@/lib/voiceControlClient");
      return {
        ...actual,
        fetchVoiceWorkerStatus: vi.fn(async () => ({ recent_events: [] })),
        listenVoiceWorker,
        speakVoiceWorker,
        startVoiceWorker: vi.fn(async () => ({ recent_events: [] })),
        stopVoiceWorker: vi.fn(),
      };
    });

    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);
    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Start voice mode" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Stop voice mode" })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Stop voice mode" }));
    expect(screen.getByRole("button", { name: "Start voice mode" })).toBeInTheDocument();

    await act(async () => {
      resolveListen({ recent_events: [{ event_type: "transcription_completed", event_id: "late-voice", summary: { normalized_transcript_text: "late text" } }] });
    });

    expect(screen.getByRole("button", { name: "Start voice mode" })).toBeInTheDocument();
    expect(speakVoiceWorker).toHaveBeenCalledTimes(1);
    const shell = await import("@/lib/shellCommands");
    expect(shell.submitChatTurnStream).not.toHaveBeenCalled();
  });

  it("rejects filler transcripts from manual voice mode without submitting a turn", async () => {
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
      BackgroundPlus: () => <div data-testid="chat-plus-background" />,
    }));
    vi.doMock("@/components/chat-messages-for-ui/agent-simple-orb", () => ({
      Orb: () => <div data-testid="agent-orb" />,
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
    const listenVoiceWorker = vi.fn(async () => ({
      recent_events: [{ event_type: "transcription_completed", event_id: "voice-filler", summary: { normalized_transcript_text: "Eh?" } }],
    }));
    const speakVoiceWorker = vi.fn(async () => ({ recent_events: [] }));
    vi.doMock("@/lib/voiceControlClient", async () => {
      const actual = await vi.importActual<typeof import("@/lib/voiceControlClient")>("@/lib/voiceControlClient");
      return {
        ...actual,
        fetchVoiceWorkerStatus: vi.fn(async () => ({ recent_events: [] })),
        listenVoiceWorker,
        speakVoiceWorker,
        startVoiceWorker: vi.fn(async () => ({ recent_events: [] })),
        stopVoiceWorker: vi.fn(),
      };
    });

    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);
    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Start voice mode" }));

    await waitFor(() => expect(listenVoiceWorker).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole("button", { name: "Start voice mode" })).toBeInTheDocument());
    expect(submitChatTurnStream).not.toHaveBeenCalled();
    expect(speakVoiceWorker).toHaveBeenCalledTimes(1);
  });
});
