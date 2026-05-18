import {
  allowlistProposalSchema,
  approvalDecisionResponseSchema,
  approvalHistorySchema,
  approvalListSchema,
  controlSnapshotSchema,
  diagnosticsSchema,
  enablementStateSchema,
  mcpMarketplaceSchema,
  memoryForgetSchema,
  memoryInspectSchema,
  policiesSchema,
  skillsMarketplaceSchema,
  traceSearchSchema,
  type ApprovalDecisionResponse,
  type ApprovalHistory,
  type ApprovalList,
  type ControlSnapshot,
  type McpMarketplace,
  type MemoryInspect,
  type SkillsMarketplace,
  type TraceSearch
} from "./schemas";

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
  return approvalDecisionResponseSchema.parse(await readJson(`/approvals/${encodeURIComponent(approvalId)}/${decision}`, { method: "POST", body: JSON.stringify({ reason }) }));
}

export async function fetchMcpMarketplace(): Promise<McpMarketplace> {
  return mcpMarketplaceSchema.parse(await readJson("/marketplace/mcp"));
}

export async function proposeMcpAllowlist(serverId: string) {
  return allowlistProposalSchema.parse(await readJson(`/marketplace/mcp/${encodeURIComponent(serverId)}/allowlist-proposals`, { method: "POST" }));
}

export async function fetchSkillsMarketplace(): Promise<SkillsMarketplace> {
  return skillsMarketplaceSchema.parse(await readJson("/marketplace/skills"));
}

export async function enableSkill(skillId: string) {
  return enablementStateSchema.parse(await readJson(`/marketplace/skills/${encodeURIComponent(skillId)}/enable`, { method: "POST" }));
}

export async function fetchMemoryInspect(): Promise<MemoryInspect> {
  return memoryInspectSchema.parse(await readJson("/memory"));
}

export async function forgetMemory(memoryId: string) {
  return memoryForgetSchema.parse(await readJson(`/memory/${encodeURIComponent(memoryId)}/forget`, { method: "POST" }));
}

export async function fetchTraceSearch(filters: { session_ref_id?: string; conversation_ref_id?: string; status?: string; approval_status?: string; tool_status?: string } = {}): Promise<TraceSearch> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return traceSearchSchema.parse(await readJson(`/traces/search${suffix}`));
}

export async function fetchApprovalHistory(): Promise<ApprovalHistory> {
  return approvalHistorySchema.parse(await readJson("/approvals/history"));
}

export async function fetchPolicies() {
  return policiesSchema.parse(await readJson("/policies"));
}

export async function fetchDiagnostics() {
  return diagnosticsSchema.parse(await readJson("/diagnostics"));
}
