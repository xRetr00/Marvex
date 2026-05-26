import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LogsView } from "./LogsView";
import { controlRequest } from "@/lib/shellCommands";

vi.mock("@/lib/shellCommands", () => ({
  controlRequest: vi.fn(async (path: string) => {
    if (path === "/logs") {
      return {
        schema_version: "1",
        logs: [{ name: "core.stderr.log", source: "control_plane", lines: ["service ready"] }],
        raw_log_payload_persisted: false,
      };
    }
    if (path === "/snapshot") {
      return {
        traces: [{ trace_id: "trace-1", event_count: 1, raw_payload_persisted: false }],
        telemetry: { trace_count: 1 },
      };
    }
    return {};
  }),
}));

describe("LogsView", () => {
  it("loads logs, traces, and telemetry from the protected Control Plane API only", async () => {
    render(<LogsView />);

    expect(await screen.findByText("core.stderr.log")).toBeInTheDocument();
    expect(await screen.findByPlaceholderText("Search logs")).toBeInTheDocument();
    expect(await screen.findByText("1 line")).toBeInTheDocument();
    expect(await screen.findByText("service ready")).toBeInTheDocument();
    expect(await screen.findByText(/trace-1/)).toBeInTheDocument();
    expect(await screen.findByText("trace count")).toBeInTheDocument();
    await waitFor(() => expect(controlRequest).toHaveBeenCalledWith("/logs", "GET"));
  });
});
