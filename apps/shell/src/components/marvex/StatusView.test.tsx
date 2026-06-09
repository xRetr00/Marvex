import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StatusView } from "./StatusView";
import { controlRequest } from "@/lib/shellCommands";

vi.mock("@/lib/shellCommands", () => ({
  controlRequest: vi.fn(async (path: string) => {
    if (path === "/snapshot") return { providers: [{ provider_id: "lmstudio", active_model: "qwen", healthy: true }], settings: { default_model: "qwen" }, telemetry: { trace_count: 1 } };
    if (path === "/voice/worker") return { wakeword_status: "enabled", lifecycle_state: "running", active_stt_backend_id: "moonshine-v2", active_tts_backend_id: "supertonic-v2", active_voice_id: "M1", process_started: true };
    if (path === "/deps") return { deps: [{ id: "browser", label: "Browser", installed: true }], features: { browser: true } };
    return {};
  }),
}));

describe("StatusView", () => {
  it("renders runtime health cards with clear hierarchy", async () => {
    render(<StatusView backend={{ ready: true, launched: true, phase: "ready", services: { runtime: "ready", voice_worker: "running" }, wakeword: "enabled" }} />);

    expect(await screen.findByText("Runtime health")).toBeInTheDocument();
    expect(await screen.findByText("Worker mesh")).toBeInTheDocument();
    expect(await screen.findByText("Voice pipeline")).toBeInTheDocument();
    expect(await screen.findByText("Provider stack")).toBeInTheDocument();
    expect(screen.queryByText("Persona / Agent")).not.toBeInTheDocument();
    expect(vi.mocked(controlRequest)).not.toHaveBeenCalledWith("/agents", "GET");
    expect(vi.mocked(controlRequest)).not.toHaveBeenCalledWith("/personas", "GET");
  });
});
