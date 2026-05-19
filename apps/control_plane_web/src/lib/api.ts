import {
  allowlistProposalSchema,
  approvalDecisionResponseSchema,
  approvalHistorySchema,
  approvalListSchema,
  autoFetchActionSchema,
  autoFetchSchema,
  connectorsSchema,
  controlSnapshotSchema,
  diagnosticsSchema,
  enablementStateSchema,
  feedbackEventsSchema,
  learningApplySchema,
  learningCandidatesSchema,
  mcpMarketplaceSchema,
  memoryForgetSchema,
  memoryInspectSchema,
  memoryTreeDailySchema,
  memoryTreeDrillDownSchema,
  memoryTreeScoringSchema,
  memoryTreeSourceSchema,
  memoryTreeTopicSchema,
  memoryTreeSearchSchema,
  policiesSchema,
  runtimePolicyAuditSchema,
  runtimePolicySchema,
  skillsMarketplaceSchema,
  sourceForgetSchema,
  sourcesSchema,
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

export async function fetchRuntimePolicy() {
  return runtimePolicySchema.parse(await readJson("/runtime-policy"));
}

export async function fetchRuntimePolicyAudit() {
  return runtimePolicyAuditSchema.parse(await readJson("/runtime-policy/audit"));
}

export async function setRuntimePolicyMode(mode: string) {
  return runtimePolicySchema.parse(await readJson("/runtime-policy", { method: "POST", body: JSON.stringify({ mode }) }));
}

export async function fetchDiagnostics() {
  return diagnosticsSchema.parse(await readJson("/diagnostics"));
}

export async function fetchFeedbackEvents() {
  return feedbackEventsSchema.parse(await readJson("/feedback"));
}

export async function fetchLearningCandidates() {
  return learningCandidatesSchema.parse(await readJson("/learning/candidates"));
}

export async function applyLearningCandidate(candidateId: string) {
  return learningApplySchema.parse(await readJson(`/learning/candidates/${encodeURIComponent(candidateId)}/apply`, { method: "POST" }));
}

export async function fetchConnectors() {
  return connectorsSchema.parse(await readJson("/connectors"));
}

export async function fetchSources() {
  return sourcesSchema.parse(await readJson("/sources"));
}

export async function fetchAutoFetch() {
  return autoFetchSchema.parse(await readJson("/autofetch"));
}

export async function fetchMemoryTreeSearch(query = "evidence") {
  return memoryTreeSearchSchema.parse(await readJson(`/memory/tree/search?q=${encodeURIComponent(query)}`));
}

export async function fetchMemoryTreeScoring() {
  return memoryTreeScoringSchema.parse(await readJson("/memory/tree/scoring"));
}
export async function setAutoFetchState(connectorId: string, action: "enable" | "disable" | "pause") {
  return autoFetchActionSchema.parse(await readJson(`/autofetch/${encodeURIComponent(connectorId)}/${action}`, { method: "POST" }));
}

export async function forgetSource(sourceId: string) {
  return sourceForgetSchema.parse(await readJson(`/sources/${encodeURIComponent(sourceId)}/forget`, { method: "POST" }));
}

export async function fetchMemorySourceTree(sourceId = "source-github") {
  return memoryTreeSourceSchema.parse(await readJson(`/memory/tree/source/${encodeURIComponent(sourceId)}`));
}

export async function fetchMemoryTopicTree(topicId = "memory-tree") {
  return memoryTreeTopicSchema.parse(await readJson(`/memory/tree/topic/${encodeURIComponent(topicId)}`));
}

export async function fetchMemoryDailyDigest(date = "2026-05-18") {
  return memoryTreeDailySchema.parse(await readJson(`/memory/tree/daily/${encodeURIComponent(date)}`));
}

export async function fetchMemoryDrillDown(chunkId = "chunk-1") {
  return memoryTreeDrillDownSchema.parse(await readJson(`/memory/tree/drill-down/${encodeURIComponent(chunkId)}`));
}
