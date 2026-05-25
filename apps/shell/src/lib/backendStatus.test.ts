import { beforeEach, describe, expect, it, vi } from "vitest";
import { controlRequest, getSetupStatus, getSupervisorStatus } from "./shellCommands";
import { fetchBackendStatus } from "./backendStatus";

vi.mock("./shellCommands", () => ({
  controlRequest: vi.fn(),
  getSetupStatus: vi.fn(),
  getSupervisorStatus: vi.fn()
}));

const mockedControlRequest = vi.mocked(controlRequest);
const mockedGetSetupStatus = vi.mocked(getSetupStatus);
const mockedGetSupervisorStatus = vi.mocked(getSupervisorStatus);

describe("fetchBackendStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetSetupStatus.mockResolvedValue({ schema_version: "1", runtime_phase: "ready", ready: true, launched: true, services: {}, manifest: null });
    mockedGetSupervisorStatus.mockResolvedValue({ voice_worker: "running" });
  });

  it("reports wake word setup when the worker is enabled but the model asset is not ready", async () => {
    mockedControlRequest.mockResolvedValue({
      wakeword_status: "enabled",
      wakeword_model_status: { readiness_status: "not_ready", readiness_blocker: "model_asset_missing_manual_install_required" },
      wakeword_supervisor_status: { asset_ready: false }
    });

    const status = await fetchBackendStatus();

    expect(status.wakeword).toBe("not_ready");
  });
});
