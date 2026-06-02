import { z } from "zod";

export const riskLevelSchema = z.enum(["safe", "low", "medium", "high", "critical"]);

export const approvalSummarySchema = z.object({
  schema_version: z.string(),
  approval_request_id: z.string(),
  trace_id: z.string(),
  turn_id: z.string(),
  capability_summary: z.object({ kind: z.string(), identifier: z.string() }),
  user_visible_summary: z.string(),
  risk_level: riskLevelSchema,
  side_effect_level: z.string(),
  execution_mode: z.string(),
  status: z.literal("pending"),
  raw_payload_persisted: z.literal(false)
});

export const approvalListSchema = z.object({
  schema_version: z.string(),
  approvals: z.array(approvalSummarySchema),
  pending_count: z.number(),
  raw_payload_persisted: z.literal(false)
});

export const approvalDecisionResponseSchema = z.object({
  schema_version: z.string(),
  approval_request_id: z.string(),
  decision_id: z.string(),
  capability_summary: z.object({ kind: z.string(), identifier: z.string() }),
  decision: z.enum(["approved", "denied"]),
  reason: z.string(),
  execution_started: z.literal(false),
  raw_payload_persisted: z.literal(false)
});

const safeRecord = z.record(z.string(), z.unknown());

export const controlSnapshotSchema = z.object({
  schema_version: z.string(),
  providers: z.array(safeRecord),
  capabilities: z.array(safeRecord),
  tools: z.array(safeRecord),
  mcp_servers: z.array(safeRecord),
  skills: z.array(safeRecord),
  traces: z.array(safeRecord),
  memory: z.array(safeRecord),
  sessions: z.array(safeRecord),
  agent_loops: z.array(safeRecord),
  telemetry: safeRecord,
  settings: safeRecord,
  raw_payload_persisted: z.literal(false),
  approvals: approvalListSchema.optional()
});

export const mcpMarketplaceSchema = z.object({
  schema_version: z.string(),
  entries: z.array(safeRecord),
  read_only_browse: z.literal(true),
  raw_payload_persisted: z.literal(false)
});

export const skillsMarketplaceSchema = z.object({
  schema_version: z.string(),
  entries: z.array(safeRecord),
  previews: z.array(safeRecord),
  raw_payload_persisted: z.literal(false)
});

export const enablementStateSchema = safeRecord;
export const allowlistProposalSchema = safeRecord;
export const dependencyInstallSchema = safeRecord;
export const mcpServerInstallSchema = safeRecord;

export const memoryInspectSchema = z.object({
  schema_version: z.string(),
  records: z.array(safeRecord),
  record_count: z.number(),
  raw_transcript_persisted: z.literal(false)
});

export const memoryForgetSchema = safeRecord;

export const traceSearchSchema = z.object({
  schema_version: z.string(),
  traces: z.array(safeRecord),
  match_count: z.number(),
  truncated: z.boolean(),
  raw_payload_persisted: z.literal(false)
});

export const approvalHistorySchema = z.object({
  schema_version: z.string(),
  decisions: z.array(approvalDecisionResponseSchema),
  decision_count: z.number(),
  raw_payload_persisted: z.literal(false)
});

export const policiesSchema = z.object({ schema_version: z.string(), policies: z.array(safeRecord), raw_payload_persisted: z.literal(false) });
export const connectorsSchema = z.object({ schema_version: z.string(), connectors: z.array(safeRecord), connector_count: z.number(), raw_token_persisted: z.literal(false) });
export const sourcesSchema = z.object({ schema_version: z.string(), sources: z.array(safeRecord), source_count: z.number(), raw_credentials_persisted: z.literal(false) });
export const autoFetchSchema = z.object({ schema_version: z.string(), policies: z.array(safeRecord), policy_count: z.number(), raw_payload_persisted: z.literal(false) });
export const memoryTreeSearchSchema = z.object({ schema_version: z.string(), query: z.string(), results: z.array(safeRecord), raw_content_persisted: z.literal(false).optional() });
export const memoryTreeScoringSchema = z.object({ schema_version: z.string(), scores: z.array(safeRecord), score_count: z.number(), raw_content_persisted: z.literal(false) });
export const memoryTreeSourceSchema = z.object({ schema_version: z.string(), tree: safeRecord, raw_content_persisted: z.literal(false) });
export const memoryTreeTopicSchema = z.object({ schema_version: z.string(), tree: safeRecord, raw_content_persisted: z.literal(false) });
export const memoryTreeDailySchema = z.object({ schema_version: z.string(), daily_digest: safeRecord, raw_content_persisted: z.literal(false) });
export const memoryTreeDrillDownSchema = z.object({ schema_version: z.string(), evidence: safeRecord });
export const autoFetchActionSchema = z.object({ schema_version: z.string(), connector_id: z.string(), requested_state: z.string(), sync_started: z.literal(false), raw_payload_persisted: z.literal(false) });
export const sourceForgetSchema = z.object({ schema_version: z.string(), source_id: z.string(), delete_started: z.literal(false), requires_memory_runtime_policy: z.literal(true), raw_content_persisted: z.literal(false) });
export const runtimePolicySchema = z.object({ schema_version: z.string(), mode: z.string(), matrix: z.record(z.string(), z.string()), audit_records: z.array(safeRecord), hard_block_blacklist_only: z.literal(true), read_list_search_allowed_by_default: z.literal(true), side_effects_policy_controlled: z.literal(true), raw_payload_persisted: z.literal(false) }).passthrough();
export const runtimePolicyAuditSchema = z.object({ schema_version: z.string(), audit_records: z.array(safeRecord), audit_count: z.number(), raw_payload_persisted: z.literal(false) });
export const diagnosticsSchema = safeRecord;
export const feedbackEventsSchema = z.object({ schema_version: z.string(), events: z.array(safeRecord), event_count: z.number(), raw_feedback_persisted: z.literal(false) });
export const learningCandidatesSchema = z.object({ schema_version: z.string(), memory_candidates: z.array(safeRecord), skill_candidates: z.array(safeRecord), policy_candidates: z.array(safeRecord), preference_candidates: z.array(safeRecord), route_candidates: z.array(safeRecord), memory_scoring_changes: z.array(safeRecord).optional(), raw_feedback_persisted: z.literal(false) });
export const learningApplySchema = safeRecord;
export const voiceStatusSchema = safeRecord;
export const voiceActionSchema = safeRecord;
export const logsSchema = z.object({
  schema_version: z.string(),
  logs: z.array(z.object({
    name: z.string(),
    source: z.string().optional(),
    lines: z.array(z.string())
  })),
  raw_log_payload_persisted: z.literal(false)
});

export const providerControlSchema = z.object({
  schema_version: z.string(),
  active_provider_id: z.string(),
  providers: z.array(safeRecord),
  raw_secret_persisted: z.literal(false).optional()
});

export type SafeRecord = z.infer<typeof safeRecord>;
export type ApprovalSummary = z.infer<typeof approvalSummarySchema>;
export type ApprovalList = z.infer<typeof approvalListSchema>;
export type ControlSnapshot = z.infer<typeof controlSnapshotSchema>;
export type ApprovalDecisionResponse = z.infer<typeof approvalDecisionResponseSchema>;
export type McpMarketplace = z.infer<typeof mcpMarketplaceSchema>;
export type SkillsMarketplace = z.infer<typeof skillsMarketplaceSchema>;
export type MemoryInspect = z.infer<typeof memoryInspectSchema>;
export type TraceSearch = z.infer<typeof traceSearchSchema>;
export type ApprovalHistory = z.infer<typeof approvalHistorySchema>;
export type Connectors = z.infer<typeof connectorsSchema>;
export type Sources = z.infer<typeof sourcesSchema>;
export type AutoFetch = z.infer<typeof autoFetchSchema>;
export type MemoryTreeSearch = z.infer<typeof memoryTreeSearchSchema>;
export type MemoryTreeScoring = z.infer<typeof memoryTreeScoringSchema>;
export type MemoryTreeSource = z.infer<typeof memoryTreeSourceSchema>;
export type MemoryTreeTopic = z.infer<typeof memoryTreeTopicSchema>;
export type MemoryTreeDaily = z.infer<typeof memoryTreeDailySchema>;
export type MemoryTreeDrillDown = z.infer<typeof memoryTreeDrillDownSchema>;
export type RuntimePolicy = z.infer<typeof runtimePolicySchema>;
export type RuntimePolicyAudit = z.infer<typeof runtimePolicyAuditSchema>;
export type FeedbackEvents = z.infer<typeof feedbackEventsSchema>;
export type LearningCandidates = z.infer<typeof learningCandidatesSchema>;
export type VoiceStatus = z.infer<typeof voiceStatusSchema>;
export type ProviderControl = z.infer<typeof providerControlSchema>;
export type LogsPayload = z.infer<typeof logsSchema>;
