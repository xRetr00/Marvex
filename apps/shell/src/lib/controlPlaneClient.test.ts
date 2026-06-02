import { beforeEach, describe, expect, it, vi } from "vitest";
import { decideApproval, fetchPendingApprovals } from "./controlPlaneClient";
import { controlRequest } from "./shellCommands";

vi.mock("./shellCommands", () => ({
  controlRequest: vi.fn()
}));

const mockedControlRequest = vi.mocked(controlRequest);

describe("control plane approval client", () => {
  beforeEach(() => {
    mockedControlRequest.mockReset();
  });

  it("parses safe pending approval projections", async () => {
    mockedControlRequest.mockResolvedValueOnce({
      approvals: [{
        approval_request_id: "approval-1",
        trace_id: "trace-1",
        turn_id: "turn-1",
        user_visible_summary: "Write file C:\\tmp\\note.txt",
        risk_level: "high",
        status: "pending",
        raw_payload_persisted: false
      }],
      pending_count: 1,
      raw_payload_persisted: false
    });

    await expect(fetchPendingApprovals()).resolves.toMatchObject([
      { approval_request_id: "approval-1", status: "pending", raw_payload_persisted: false }
    ]);
    expect(mockedControlRequest).toHaveBeenCalledWith("/approvals");
  });

  it("sends approval decisions to explicit decision endpoints", async () => {
    mockedControlRequest.mockResolvedValueOnce({ status: "approved" });

    await expect(decideApproval("approval/1", "approve", "User approved")).resolves.toEqual({ status: "approved" });

    expect(mockedControlRequest).toHaveBeenCalledWith(
      "/approvals/approval%2F1/approve",
      "POST",
      { reason: "User approved" }
    );
  });
});
