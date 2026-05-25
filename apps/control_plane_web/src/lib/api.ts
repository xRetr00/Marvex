import {
  allowlistProposalSchema,
  agentCatalogSchema,
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
  personaCatalogSchema,
  runtimePolicyAuditSchema,
  runtimePolicySchema,
  skillsMarketplaceSchema,
  sourceForgetSchema,
  sourcesSchema,
  traceSearchSchema,
  voiceActionSchema,
  voiceStatusSchema,
  type ApprovalDecisionResponse,
  type ApprovalHistory,
  type ApprovalList,
  type AgentCatalog,
  type ControlSnapshot,
  type McpMarketplace,
  type MemoryInspect,
  type PersonaCatalog,
  type SkillsMarketplace,
  type TraceSearch
} from "./schemas";

const BASE_URL = "/control";

export class ControlPlaneApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
  }
}

async function readJson(path: string, init: RequestInit = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
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

export async function fetchVoiceStatus() {
  return voiceStatusSchema.parse(await readJson("/voice"));
}

export async function selectVoiceStt(payload: { main_backend_id: string; fallback_backend_id: string }) {
  return voiceActionSchema.parse(await readJson("/voice/stt/select", { method: "POST", body: JSON.stringify(payload) }));
}

export async function selectVoiceTts(payload: { main_backend_id: string; fallback_backend_id: string; active_voice_id: string }) {
  return voiceActionSchema.parse(await readJson("/voice/tts/select", { method: "POST", body: JSON.stringify(payload) }));
}

export async function updateWakeword(always_listening_enabled: boolean) {
  return voiceActionSchema.parse(await readJson("/voice/wakeword", { method: "POST", body: JSON.stringify({ always_listening_enabled }) }));
}

export async function updateVoiceVad() {
  return voiceActionSchema.parse(await readJson("/voice/vad", { method: "POST", body: JSON.stringify({ aggressiveness: 2, noisy_room_handling_enabled: true }) }));
}

export async function updateVoiceBargeIn() {
  return voiceActionSchema.parse(await readJson("/voice/barge-in", { method: "POST", body: JSON.stringify({ enabled: true, cancel_queued_tts: true }) }));
}

export async function updateVoiceEarlySpeech() {
  return voiceActionSchema.parse(await readJson("/voice/early-speech", { method: "POST", body: JSON.stringify({ enabled: true, min_interval_ms: 8000 }) }));
}

export async function updateVoicePersonality() {
  return voiceActionSchema.parse(await readJson("/voice/personality", { method: "POST", body: JSON.stringify({ filler_frequency: "medium", confirmation_style: "short", sensitive_content_policy: "ask", auto_speak_enabled: true, speak_confirmations: true }) }));
}

export async function updateVoiceRetention() {
  return voiceActionSchema.parse(await readJson("/voice/retention", { method: "POST", body: JSON.stringify({ raw_audio_persistence_allowed: false, transcript_persistence_allowed: false, generated_audio_persistence_allowed: false }) }));
}

export async function downloadVoiceModel(payload: { model_id: string; backend_id: string; model_kind: string; source_uri: string }) {
  return voiceActionSchema.parse(await readJson("/voice/models/download", { method: "POST", body: JSON.stringify(payload) }));
}

export async function removeVoiceModel(payload: { model_id: string; model_kind: string }) {
  return voiceActionSchema.parse(await readJson("/voice/models/remove", { method: "POST", body: JSON.stringify(payload) }));
}

export async function testVoiceStt() {
  return voiceActionSchema.parse(await readJson("/voice/test-stt", { method: "POST", body: JSON.stringify({ test_id: "control-plane-stt", backend_id: "moonshine-v2", sample_ref_id: "control-plane-sample" }) }));
}

export async function testVoiceTts() {
  return voiceActionSchema.parse(await readJson("/voice/test-tts", { method: "POST", body: JSON.stringify({ test_id: "control-plane-tts", backend_id: "kokoro-onnx", phrase: "Testing voice." }) }));
}

export async function fetchVoiceWorkerStatus() {
  return voiceActionSchema.parse(await readJson("/voice/worker"));
}

export async function fetchVoiceWorkerDevices() {
  return voiceActionSchema.parse(await readJson("/voice/worker/devices"));
}

export async function startVoiceWorker() {
  return voiceActionSchema.parse(await readJson("/voice/worker/start", { method: "POST" }));
}

export async function stopVoiceWorker() {
  return voiceActionSchema.parse(await readJson("/voice/worker/stop", { method: "POST" }));
}

export async function pauseVoiceWorker() {
  return voiceActionSchema.parse(await readJson("/voice/worker/pause", { method: "POST" }));
}

export async function resumeVoiceWorker() {
  return voiceActionSchema.parse(await readJson("/voice/worker/resume", { method: "POST" }));
}

export async function reloadVoiceWorkerConfig(payload: { input_device_id?: string; output_device_id?: string; sample_rate?: number; channel_count?: number }) {
  return voiceActionSchema.parse(await readJson("/voice/worker/reload-config", { method: "POST", body: JSON.stringify(payload) }));
}

export async function testVoiceWorkerMic() {
  return voiceActionSchema.parse(await readJson("/voice/worker/test-mic", { method: "POST", body: JSON.stringify({ device_id: "input-default" }) }));
}

export async function testVoiceWorkerPlayback() {
  return voiceActionSchema.parse(await readJson("/voice/worker/test-playback", { method: "POST", body: JSON.stringify({ device_id: "output-default" }) }));
}

export async function testVoiceWorkerWakeword() {
  return voiceActionSchema.parse(await readJson("/voice/worker/test-wakeword", { method: "POST" }));
}

export async function fetchVoiceWorkerWakewordSupervisor() {
  return voiceActionSchema.parse(await readJson("/voice/worker/wakeword-supervisor"));
}

export async function fetchAgents(): Promise<AgentCatalog> {
  return agentCatalogSchema.parse(await readJson("/agents"));
}

export async function selectAgent(agentId: string): Promise<AgentCatalog> {
  return agentCatalogSchema.parse(await readJson("/agents/active", { method: "POST", body: JSON.stringify({ agent_id: agentId }) }));
}

export async function fetchPersonas(): Promise<PersonaCatalog> {
  return personaCatalogSchema.parse(await readJson("/personas"));
}

export async function selectPersona(personaId: string): Promise<PersonaCatalog> {
  return personaCatalogSchema.parse(await readJson("/personas/active", { method: "POST", body: JSON.stringify({ persona_id: personaId }) }));
}

export async function startVoiceWorkerWakewordSupervisor() {
  return voiceActionSchema.parse(await readJson("/voice/worker/wakeword-supervisor/start", { method: "POST" }));
}

export async function stopVoiceWorkerWakewordSupervisor() {
  return voiceActionSchema.parse(await readJson("/voice/worker/wakeword-supervisor/stop", { method: "POST" }));
}

export async function tickVoiceWorkerWakewordSupervisor() {
  return voiceActionSchema.parse(await readJson("/voice/worker/wakeword-supervisor/tick", { method: "POST" }));
}

export async function testVoiceWorkerStt() {
  return voiceActionSchema.parse(await readJson("/voice/worker/test-stt", { method: "POST" }));
}

export async function testVoiceWorkerTts() {
  return voiceActionSchema.parse(await readJson("/voice/worker/test-tts", { method: "POST" }));
}
export async function switchVoiceWorkerSttBackend(payload: { backend_id: string }) {
  return voiceActionSchema.parse(await readJson("/voice/worker/stt/switch", { method: "POST", body: JSON.stringify(payload) }));
}

export async function switchVoiceWorkerTtsBackend(payload: { backend_id: string }) {
  return voiceActionSchema.parse(await readJson("/voice/worker/tts/switch", { method: "POST", body: JSON.stringify(payload) }));
}

export async function switchVoiceWorkerActiveVoice(payload: { voice_id: string }) {
  return voiceActionSchema.parse(await readJson("/voice/worker/voice/switch", { method: "POST", body: JSON.stringify(payload) }));
}

export async function installVoiceWorkerModel(payload: { model_id: string; backend_id: string; model_kind: string; relative_path: string }) {
  return voiceActionSchema.parse(await readJson("/voice/worker/models/install", { method: "POST", body: JSON.stringify({ ...payload, explicit_user_triggered: true }) }));
}

export async function removeVoiceWorkerModel(payload: { model_id: string }) {
  return voiceActionSchema.parse(await readJson("/voice/worker/models/remove", { method: "POST", body: JSON.stringify(payload) }));
}
