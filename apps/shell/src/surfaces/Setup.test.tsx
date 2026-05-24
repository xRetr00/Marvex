import { act, render, screen } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SetupPage } from "./Setup";
import { markSetupDone } from "@/lib/modeStore";

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
  startSetup: vi.fn(async () => ({ runtime_phase: "uv_unavailable" }))
}));

vi.mock("@/lib/modeStore", () => ({
  markSetupDone: vi.fn()
}));

vi.mock("@/components/scramble-text", () => ({
  ScrambleText: ({ text }: { text: string }) => <span>{text}</span>
}));

const mockedMarkSetupDone = vi.mocked(markSetupDone);

describe("SetupPage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockedMarkSetupDone.mockClear();
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
});
