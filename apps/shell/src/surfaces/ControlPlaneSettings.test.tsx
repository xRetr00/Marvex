import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ControlPlaneSettings } from "./ControlPlaneSettings";
import { controlRequest, openControlPlane } from "@/lib/shellCommands";

vi.mock("@/lib/shellCommands", () => ({
  controlRequest: vi.fn(),
  openControlPlane: vi.fn(),
}));

const mockedControlRequest = vi.mocked(controlRequest);
const mockedOpenControlPlane = vi.mocked(openControlPlane);

describe("ControlPlaneSettings", () => {
  beforeEach(() => {
    let secretPresent = false;
    let runtimeMode = "ask_before_risky";
    mockedControlRequest.mockReset();
    mockedOpenControlPlane.mockReset();
    mockedControlRequest.mockImplementation(async (path: string, method = "GET", body?: unknown) => {
      if (path === "/runtime-policy") {
        if (method === "POST") runtimeMode = String((body as { mode: string }).mode);
        return {
          schema_version: "1",
          mode: runtimeMode,
          matrix: { file_delete: runtimeMode === "auto_marvex" ? "allow" : "ask" },
          raw_payload_persisted: false,
        };
      }
      if (path === "/providers" || path.startsWith("/providers/")) {
        if (path.endsWith("/secret") && method === "POST") secretPresent = true;
        if (path.endsWith("/secret") && method === "DELETE") secretPresent = false;
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
              automation_model: "qwen2.5-coder-7b",
              models: ["qwen2.5-coder-7b", "llama-3.1-8b"],
              multi_models: ["qwen2.5-coder-7b"],
              base_url: "http://127.0.0.1:1234/v1",
              provider_mode: "openai_compatible",
              supports_custom_base_url: true,
              automation_model_capabilities: { vision: false },
              automation_policy: { vision_required: false },
              automation_validation: { ready: true, reason_code: null },
              secret_present: secretPresent,
              secret_display: secretPresent ? "sk-p****cret" : "",
              secret_value_present: false,
            },
          ],
          raw_secret_persisted: false,
        };
      }
      if (path === "/deps") return { deps: [{ id: "browser", label: "Browser automation", group: "browser", installed: false, feature: "browser" }], features: { tts: true, stt: true, wakeword: true, web_search: true, browser: false, mcp: false, computer_use: false, embeddings: false } };
      if (path === "/deps/install") return { id: "browser", status: "installed", detail: "pip_install_succeeded" };
      if (path === "/web-search") {
        return {
          schema_version: "1",
          primary_provider: "searxng",
          fallback_provider: "ddgs",
          provider_order: ["searxng", "ddgs"],
          searxng_base_url: method === "POST" ? String((body as { searxng_base_url: string }).searxng_base_url) : "http://127.0.0.1:8888",
          raw_payload_persisted: false,
        };
      }
      if (path === "/logs") return { schema_version: "1", logs: [{ name: "core.stderr.log", source: "control", lines: ["service ready"] }], raw_log_payload_persisted: false };
      if (path === "/snapshot") return { schema_version: "1", traces: [{ trace_id: "trace-1", event_count: 2 }], telemetry: { trace_count: 1 }, raw_payload_persisted: false };
      if (path === "/marketplace/mcp") return { schema_version: "1", entries: [{ server_id: "local-mcp", install_allowed: true, required_dep_group_id: "mcp" }], read_only_browse: true, raw_payload_persisted: false };
      if (path === "/marketplace/skills") return { schema_version: "1", entries: [{ skill_id: "skill.planning", script_execution_allowed: false }], previews: [], raw_payload_persisted: false };
      return {};
    });
  });

  it("renders real control data and masks submitted provider secrets", async () => {
    render(<ControlPlaneSettings />);

    expect((await screen.findAllByText("LM Studio")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Provider stack")).toBeInTheDocument();
    expect(await screen.findByText("Model routing")).toBeInTheDocument();
    expect(await screen.findByText("Automation readiness")).toBeInTheDocument();
    expect(await screen.findByText("Runtime policy")).toBeInTheDocument();
    expect(await screen.findByText("Web search")).toBeInTheDocument();
    expect(await screen.findByLabelText("SearXNG URL")).toHaveValue("http://127.0.0.1:8888");
    expect(await screen.findByLabelText("Multi-model candidate")).toBeInTheDocument();
    expect(await screen.findByText("Browser automation")).toBeInTheDocument();
    expect(await screen.findByText("trace-1")).toBeInTheDocument();
    expect((await screen.findAllByText("local-mcp")).length).toBeGreaterThan(0);
    expect(await screen.findByText("skill.planning")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Active provider"), "lmstudio_responses");
    await userEvent.selectOptions(screen.getByLabelText("Active model"), "llama-3.1-8b");
    await userEvent.selectOptions(screen.getByLabelText("Multi-model candidate"), "llama-3.1-8b");
    await userEvent.click(screen.getByRole("button", { name: /Add multi-model/i }));
    await userEvent.selectOptions(screen.getByLabelText("Provider mode"), "openai_compatible");
    await userEvent.clear(screen.getByLabelText("Provider base URL"));
    await userEvent.type(screen.getByLabelText("Provider base URL"), "http://localhost:20128/v1");
    await userEvent.click(screen.getByRole("button", { name: /Save endpoint/i }));
    await userEvent.clear(screen.getByLabelText("Automation model id"));
    await userEvent.type(screen.getByLabelText("Automation model id"), "gpt-4o");
    await userEvent.click(screen.getByLabelText("Selected automation model supports vision"));
    await userEvent.click(screen.getByLabelText("Require vision for browser/computer tasks"));
    await userEvent.click(screen.getByRole("button", { name: /Save automation model/i }));
    await userEvent.selectOptions(screen.getByLabelText("Tool approval mode"), "auto_marvex");
    await userEvent.click(screen.getByRole("button", { name: /Save mode/i }));
    await userEvent.clear(screen.getByLabelText("SearXNG URL"));
    await userEvent.type(screen.getByLabelText("SearXNG URL"), "http://127.0.0.1:7777");
    await userEvent.click(screen.getByRole("button", { name: /Save SearXNG URL/i }));
    await userEvent.type(screen.getByLabelText("Provider API key"), "sk-plain-text-secret");
    await userEvent.click(screen.getByRole("button", { name: /Save key/i }));
    await userEvent.click(screen.getByRole("button", { name: /Install Browser automation/i }));
    await userEvent.click(screen.getByRole("button", { name: /Install MCP dependency mcp/i }));
    await userEvent.click(screen.getByRole("button", { name: /Open full control plane/i }));

    await waitFor(() => expect(mockedControlRequest).toHaveBeenCalledWith("/providers/lmstudio_responses/connection", "POST", { base_url: "http://localhost:20128/v1", provider_mode: "openai_compatible" }));
    expect(mockedControlRequest).toHaveBeenCalledWith("/providers/lmstudio_responses/models/multi", "POST", { models: ["qwen2.5-coder-7b", "llama-3.1-8b"] });
    expect(mockedControlRequest).toHaveBeenCalledWith("/providers/lmstudio_responses/automation", "POST", { model: "gpt-4o", supports_vision: true, vision_required: true });
    expect(mockedControlRequest).toHaveBeenCalledWith("/runtime-policy", "POST", { mode: "auto_marvex" });
    expect(mockedControlRequest).toHaveBeenCalledWith("/web-search", "POST", { searxng_base_url: "http://127.0.0.1:7777" });
    await waitFor(() => expect(mockedControlRequest).toHaveBeenCalledWith("/providers/lmstudio_responses/secret", "POST", { secret: "sk-plain-text-secret" }));
    expect(mockedControlRequest).toHaveBeenCalledWith("/deps/install", "POST", { id: "browser" });
    expect(mockedControlRequest).toHaveBeenCalledWith("/deps/install", "POST", { id: "mcp" });
    expect(mockedOpenControlPlane).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("sk-plain-text-secret")).not.toBeInTheDocument();
    expect(await screen.findByText("sk-p****cret")).toBeInTheDocument();
    expect(screen.getByText("core.stderr.log")).toBeInTheDocument();
  }, 20000);
});
