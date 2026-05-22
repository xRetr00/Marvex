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

export async function fetchPendingApprovals(): Promise<ApprovalSummary[]> {
  const payload = approvalListSchema.parse(await controlRequest("/approvals"));
  return payload.approvals;
}

export async function decideApproval(approvalId: string, decision: "approve" | "deny" | "cancel", reason: string): Promise<unknown> {
  return controlRequest(`/approvals/${encodeURIComponent(approvalId)}/${decision}`, "POST", { reason });
}
