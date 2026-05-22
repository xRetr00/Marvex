import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SpotlightSurface } from "./Spotlight";

vi.mock("../lib/tauriBridge", () => ({ listen: vi.fn(async () => vi.fn()) }));
vi.mock("../lib/controlPlaneClient", () => ({
  fetchPendingApprovals: vi.fn(async () => [{ approval_request_id: "approval-1", user_visible_summary: "Run safe action?", risk_level: "medium", status: "pending", raw_payload_persisted: false }]),
  decideApproval: vi.fn()
}));

describe("SpotlightSurface", () => {
  it("renders pending approvals from the protected control plane client", async () => {
    render(<SpotlightSurface />);
    await waitFor(() => expect(screen.getByText("Run safe action?")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Deny/i })).toBeInTheDocument();
  });
});
