import { z } from "zod";
import { controlRequest } from "./shellCommands";

export const approvalSchema = z.object({
  approval_request_id: z.string(),
  trace_id: z.string().optional(),
  turn_id: z.string().optional(),
  user_visible_summary: z.string(),
  risk_level: z.string(),
  status: z.literal("pending"),
  raw_payload_persisted: z.literal(false)
}).passthrough();

const approvalListSchema = z.object({
  approvals: z.array(approvalSchema),
  pending_count: z.number(),
  raw_payload_persisted: z.literal(false)
}).passthrough();

export type ApprovalSummary = z.infer<typeof approvalSchema>;

export const agentProfileSchema = z.object({
  agent_id: z.string(),
  display_name: z.string(),
  role: z.string(),
  allowed_intents: z.array(z.string()).default([]),
  default_capability_refs: z.array(z.string()).default([]),
  default_skill_refs: z.array(z.string()).default([]),
  direct_selectable: z.boolean().default(true),
  can_spawn_subagents: z.boolean().default(false),
  spawnable_agent_ids: z.array(z.string()).default([]),
  max_subagents_per_turn: z.number().default(0),
  raw_prompt_persisted: z.literal(false)
}).passthrough();

export const agentCatalogSchema = z.object({
  schema_version: z.string(),
  active_agent_id: z.string(),
  agents: z.array(agentProfileSchema),
  agent_count: z.number(),
  selectable_count: z.number().optional(),
  raw_payload_persisted: z.literal(false)
}).passthrough();

export const personaProfileSchema = z.object({
  persona_id: z.string(),
  display_name: z.string(),
  assistant_identity: z.string(),
  voice_id: z.string(),
  voice_gender_presentation: z.string(),
  speaking_style: z.string(),
  raw_prompt_persisted: z.literal(false)
}).passthrough();

export const personaCatalogSchema = z.object({
  schema_version: z.string(),
  active_persona_id: z.string(),
  personas: z.array(personaProfileSchema),
  persona_count: z.number(),
  raw_payload_persisted: z.literal(false)
}).passthrough();

export type AgentCatalog = z.infer<typeof agentCatalogSchema>;
export type AgentProfile = z.infer<typeof agentProfileSchema>;
export type PersonaCatalog = z.infer<typeof personaCatalogSchema>;
export type PersonaProfile = z.infer<typeof personaProfileSchema>;

export async function fetchPendingApprovals(): Promise<ApprovalSummary[]> {
  const payload = approvalListSchema.parse(await controlRequest("/approvals"));
  return payload.approvals;
}

export async function decideApproval(approvalId: string, decision: "approve" | "deny" | "cancel", reason: string): Promise<unknown> {
  return controlRequest(`/approvals/${encodeURIComponent(approvalId)}/${decision}`, "POST", { reason });
}

export async function fetchAgentCatalog(): Promise<AgentCatalog> {
  return agentCatalogSchema.parse(await controlRequest("/agents"));
}

export async function selectActiveAgent(agentId: string): Promise<AgentCatalog> {
  return agentCatalogSchema.parse(await controlRequest("/agents/active", "POST", { agent_id: agentId }));
}

export async function fetchPersonaCatalog(): Promise<PersonaCatalog> {
  return personaCatalogSchema.parse(await controlRequest("/personas"));
}

export async function selectActivePersona(personaId: string): Promise<PersonaCatalog> {
  return personaCatalogSchema.parse(await controlRequest("/personas/active", "POST", { persona_id: personaId }));
}
