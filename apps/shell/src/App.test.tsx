import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

describe("App shell fallback", () => {
  it("shows a visible fallback if the chat surface chunk fails", async () => {
    vi.resetModules();
    vi.doMock("./lib/modeStore", () => ({
      getPersistedMode: () => "chat",
      isSetupDone: () => true,
    }));
    vi.doMock("./lib/shellCommands", () => ({
      showChat: vi.fn(async () => undefined),
      showOverlay: vi.fn(async () => undefined),
    }));
    vi.doMock("./surfaces/ChatApp", () => {
      throw new Error("chat surface unavailable");
    });

    const { App } = await import("./App");
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Marvex could not load this window.")).toBeInTheDocument();
    });
  });
});
