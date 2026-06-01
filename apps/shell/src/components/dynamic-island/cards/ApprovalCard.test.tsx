import { render, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApprovalCard } from "./ApprovalCard";
import type { ApprovalSummary } from "@/lib/controlPlaneClient";

const decideApproval = vi.fn();
const resumeApprovalTurn = vi.fn();

vi.mock("@/lib/controlPlaneClient", () => ({
  decideApproval: (...args: unknown[]) => decideApproval(...args),
}));
vi.mock("@/lib/shellCommands", () => ({
  resumeApprovalTurn: (...args: unknown[]) => resumeApprovalTurn(...args),
}));

function makeApproval(overrides: Partial<ApprovalSummary> = {}): ApprovalSummary {
  return {
    approval_request_id: "appr-1",
    trace_id: "trace-1",
    turn_id: "turn-1",
    user_visible_summary: "Delete 3 files in Documents?",
    risk_level: "high",
    status: "pending",
    raw_payload_persisted: false,
    ...overrides,
  } as ApprovalSummary;
}

beforeEach(() => {
  decideApproval.mockReset().mockResolvedValue({});
  resumeApprovalTurn.mockReset().mockResolvedValue({});
});

describe("ApprovalCard", () => {
  it("approves: decides then resumes the turn, then signals done", async () => {
    const onDone = vi.fn();
    const { container } = render(<ApprovalCard approval={makeApproval()} onDone={onDone} />);

    await userEvent.click(within(container).getByRole("button", { name: /approve/i }));

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(decideApproval).toHaveBeenCalledWith("appr-1", "approve", expect.any(String));
    expect(resumeApprovalTurn).toHaveBeenCalledWith(
      expect.objectContaining({ decision: "approve", traceId: "trace-1", turnId: "turn-1", approvalId: "appr-1" }),
    );
  });

  it("denies: passes the deny decision to the control plane", async () => {
    const onDone = vi.fn();
    const { container } = render(<ApprovalCard approval={makeApproval()} onDone={onDone} />);

    await userEvent.click(within(container).getByRole("button", { name: /deny/i }));

    await waitFor(() => expect(decideApproval).toHaveBeenCalledWith("appr-1", "deny", expect.any(String)));
  });

  it("still decides (and is clickable) when trace/turn ids are missing — no permanently-dead buttons", async () => {
    const onDone = vi.fn();
    const { container } = render(
      <ApprovalCard approval={makeApproval({ trace_id: undefined, turn_id: undefined })} onDone={onDone} />,
    );

    const approve = within(container).getByRole("button", { name: /approve/i });
    expect(approve).not.toBeDisabled();

    await userEvent.click(approve);

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(decideApproval).toHaveBeenCalledWith("appr-1", "approve", expect.any(String));
    expect(resumeApprovalTurn).not.toHaveBeenCalled();
  });
});
