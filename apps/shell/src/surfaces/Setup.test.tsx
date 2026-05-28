import { act, render, screen } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SetupPage } from "./Setup";
import { markSetupDone } from "@/lib/modeStore";
import { fetchDeps } from "@/lib/depsClient";
import { getBackendHealth, getSetupStatus } from "@/lib/shellCommands";

vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  motion: new Proxy({}, {
    get: () => ({ children, ...props }: { children: React.ReactNode }) =>
      <div {...props}>{children}</div>
  })
}));

vi.mock("@/components/animated-progress-bar", () => ({
  default: ({ value }: { value: number }) => <div data-progress={value} />
}));

vi.mock("@/lib/depsClient", () => ({
  fetchDeps: vi.fn(async () => ({ deps: [] })),
  installDep: vi.fn()
}));

vi.mock("@/lib/shellCommands", () => ({
  getSetupStatus: vi.fn(async () => ({ runtime_phase: "uv_unavailable" })),
  startSetup: vi.fn(async () => ({ runtime_phase: "uv_unavailable" })),
  getBackendHealth: vi.fn(async () => ({ reachable: false }))
}));

vi.mock("@/lib/modeStore", () => ({
  markSetupDone: vi.fn()
}));

vi.mock("@/components/scramble-text", () => ({
  ScrambleText: ({ text }: { text: string }) => <span>{text}</span>
}));

const mockedMarkSetupDone = vi.mocked(markSetupDone);
const mockedFetchDeps = vi.mocked(fetchDeps);
const mockedGetBackendHealth = vi.mocked(getBackendHealth);
const mockedGetSetupStatus = vi.mocked(getSetupStatus);

describe("SetupPage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockedMarkSetupDone.mockClear();
    mockedFetchDeps.mockReset();
    mockedFetchDeps.mockResolvedValue({ deps: [], features: { tts: true, stt: true, wakeword: true, web_search: true, browser: true, embeddings: true } });
    mockedGetBackendHealth.mockReset();
    mockedGetBackendHealth.mockResolvedValue({ reachable: false });
    mockedGetSetupStatus.mockReset();
    mockedGetSetupStatus.mockResolvedValue({ runtime_phase: "uv_unavailable", schema_version: "1", ready: false, launched: false, services: {}, manifest: null });
  });

  it("keeps first-run setup pending when runtime setup fails", async () => {
    const onComplete = vi.fn();

    render(<SetupPage onComplete={onComplete} />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      vi.advanceTimersByTime(2500);
      await Promise.resolve();
      await Promise.resolve();
    });
    screen.getByText("Runtime setup failed. See logs (runtime.bootstrap.log).");

    expect(mockedMarkSetupDone).not.toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("waits for backend reachability after runtime becomes ready before completing setup", async () => {
    const onComplete = vi.fn();
    mockedGetSetupStatus.mockResolvedValue({ runtime_phase: "ready", schema_version: "1", ready: false, launched: true, services: { runtime: "ready" }, manifest: null });
    mockedGetBackendHealth
      .mockResolvedValueOnce({ reachable: false })
      .mockResolvedValueOnce({ reachable: true, status_code: 200, health: {} });

    render(<SetupPage onComplete={onComplete} />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mockedFetchDeps).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockedFetchDeps).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(900);
      await Promise.resolve();
    });
    expect(mockedMarkSetupDone).toHaveBeenCalled();
    expect(onComplete).toHaveBeenCalled();
  });
});
