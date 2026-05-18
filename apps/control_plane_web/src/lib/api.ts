import { approvalDecisionResponseSchema, approvalListSchema, controlSnapshotSchema, type ApprovalDecisionResponse, type ApprovalList, type ControlSnapshot } from "./schemas";

const BASE_URL = "/control";

export class ControlPlaneApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
  }
}

function authHeaders(): HeadersInit {
  const sessionToken = window.sessionStorage.getItem("marvex_control_plane_token");
  return sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {};
}

async function readJson(path: string, init: RequestInit = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...init.headers
    }
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new ControlPlaneApiError(payload?.message ?? "Control Plane request failed", response.status);
  }
  return payload;
}

export async function fetchSnapshot(): Promise<ControlSnapshot> {
  return controlSnapshotSchema.parse(await readJson("/snapshot"));
}

export async function fetchApprovals(): Promise<ApprovalList> {
  return approvalListSchema.parse(await readJson("/approvals"));
}

export async function decideApproval(approvalId: string, decision: "approve" | "deny", reason: string): Promise<ApprovalDecisionResponse> {
  return approvalDecisionResponseSchema.parse(
    await readJson(`/approvals/${encodeURIComponent(approvalId)}/${decision}`, {
      method: "POST",
      body: JSON.stringify({ reason })
    })
  );
}