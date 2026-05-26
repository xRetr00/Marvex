import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
  });

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
      marvexRestart: vi.fn(),
      marvexShutdown: vi.fn(),
      showOverlay: vi.fn(),
      startBackend: vi.fn(),
      submitChatTurn: vi.fn(),
    }));
    vi.doMock("@/lib/voiceControlClient", () => ({
      startVoiceWorker: vi.fn(),
      stopVoiceWorker: vi.fn(),
    }));

    const { ChatApp } = await import("./ChatApp");
    render(<ChatApp />);

    await waitFor(() => expect(screen.queryByText("startup")).not.toBeInTheDocument());
    const background = screen.getByTestId("chat-plus-background");
    expect(background).toHaveAttribute("data-plus-color", "#fb3a5d");
    expect(background.className).toContain("pointer-events-none");
  });
});
