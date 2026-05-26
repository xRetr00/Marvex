import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

describe("App shell fallback", () => {
  it("shows a visible 404 page for unknown shell routes", async () => {
    vi.resetModules();
    window.history.pushState({}, "", "/missing-shell-route");
    vi.doMock("./lib/modeStore", () => ({
      getPersistedMode: () => "chat",
      isSetupDone: () => true,
    }));
    vi.doMock("./lib/shellCommands", () => ({
      showChat: vi.fn(async () => undefined),
      showOverlay: vi.fn(async () => undefined),
    }));
    vi.doMock("./surfaces/ChatApp", () => ({
      ChatApp: () => <div>chat surface</div>,
    }));

    const { App } = await import("./App");
    render(<App />);

    expect(screen.getByText("Window not found")).toBeInTheDocument();
    expect(screen.getByText("/missing-shell-route")).toBeInTheDocument();
  });

  it("shows a visible fallback if the chat surface chunk fails", async () => {
    vi.resetModules();
    window.history.pushState({}, "", "/");
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

  it("loads the overlay surface through an index query route for packaged builds", async () => {
    vi.resetModules();
    window.history.pushState({}, "", "/?surface=overlay");
    vi.doMock("./lib/modeStore", () => ({
      getPersistedMode: () => "overlay",
      isSetupDone: () => true,
    }));
    vi.doMock("./lib/shellCommands", () => ({
      showChat: vi.fn(async () => undefined),
      showOverlay: vi.fn(async () => undefined),
    }));
    vi.doMock("./surfaces/overlay", () => ({
      OverlaySurface: () => <div>overlay surface</div>,
    }));

    const { App } = await import("./App");
    render(<App />);

    expect(await screen.findByText("overlay surface")).toBeInTheDocument();
  });
});
