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

const safeRecord = z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null()]));

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
  settings: z.record(z.string(), z.boolean()),
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
export const diagnosticsSchema = safeRecord;

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
