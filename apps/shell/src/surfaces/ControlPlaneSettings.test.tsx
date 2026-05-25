import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ControlPlaneSettings } from "./ControlPlaneSettings";
import { controlRequest } from "@/lib/shellCommands";

vi.mock("@/lib/shellCommands", () => ({
  controlRequest: vi.fn(),
}));

const mockedControlRequest = vi.mocked(controlRequest);

describe("ControlPlaneSettings", () => {
  beforeEach(() => {
    mockedControlRequest.mockReset();
    mockedControlRequest.mockImplementation(async (path: string, method = "GET", body?: unknown) => {
      if (path === "/providers" || path.startsWith("/providers/")) {
        const active = path === "/providers/active" ? String((body as { provider_id: string }).provider_id) : "lmstudio_responses";
        return {
          schema_version: "1",
          active_provider_id: active,
          providers: [
            {
              provider_id: "lmstudio_responses",
              label: "LM Studio",
              configured: true,
              healthy: true,
              active_model: "qwen2.5-coder-7b",
              models: ["qwen2.5-coder-7b", "llama-3.1-8b"],
              multi_models: ["qwen2.5-coder-7b"],
              secret_present: path.endsWith("/secret") && method !== "DELETE",
              secret_display: path.endsWith("/secret") && method !== "DELETE" ? "********" : "",
              secret_value_present: false,
            },
          ],
          raw_secret_persisted: false,
        };
      }
      if (path === "/deps") return { deps: [{ id: "browser", label: "Browser automation", group: "browser", installed: false, feature: "browser" }], features: { tts: true, stt: true, wakeword: true, web_search: true, browser: false, embeddings: false } };
      if (path === "/deps/install") return { id: "browser", status: "installed", detail: "pip_install_succeeded" };
      if (path === "/logs") return { schema_version: "1", logs: [{ name: "core.stderr.log", source: "control", lines: ["service ready"] }], raw_log_payload_persisted: false };
      if (path === "/snapshot") return { schema_version: "1", traces: [{ trace_id: "trace-1", event_count: 2 }], telemetry: { trace_count: 1 }, raw_payload_persisted: false };
      if (path === "/marketplace/mcp") return { schema_version: "1", entries: [{ server_id: "local-mcp", install_allowed: false }], read_only_browse: true, raw_payload_persisted: false };
      if (path === "/marketplace/skills") return { schema_version: "1", entries: [{ skill_id: "skill.planning", script_execution_allowed: false }], previews: [], raw_payload_persisted: false };
      return {};
    });
  });

  it("renders real control data and masks submitted provider secrets", async () => {
    render(<ControlPlaneSettings />);

    expect((await screen.findAllByText("LM Studio")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Browser automation")).toBeInTheDocument();
    expect(await screen.findByText("trace-1")).toBeInTheDocument();
    expect(await screen.findByText("local-mcp")).toBeInTheDocument();
    expect(await screen.findByText("skill.planning")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Active provider"), "lmstudio_responses");
    await userEvent.selectOptions(screen.getByLabelText("Active model"), "llama-3.1-8b");
    await userEvent.type(screen.getByLabelText("Provider API key"), "sk-plain-text-secret");
    await userEvent.click(screen.getByRole("button", { name: /Save key/i }));
    await userEvent.click(screen.getByRole("button", { name: /Install Browser automation/i }));

    await waitFor(() => expect(mockedControlRequest).toHaveBeenCalledWith("/providers/lmstudio_responses/secret", "POST", { secret: "sk-plain-text-secret" }));
    expect(mockedControlRequest).toHaveBeenCalledWith("/deps/install", "POST", { id: "browser" });
    expect(screen.queryByText("sk-plain-text-secret")).not.toBeInTheDocument();
    expect(await screen.findByText("********")).toBeInTheDocument();
  });
});
