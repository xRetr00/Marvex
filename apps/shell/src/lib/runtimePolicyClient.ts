import { z } from "zod";
import { controlRequest } from "./shellCommands";

export const runtimePolicyModeSchema = z.enum(["auto_marvex", "ask_before_risky", "owner_safe", "locked_down"]);
export type RuntimePolicyMode = z.infer<typeof runtimePolicyModeSchema>;

export const runtimePolicySchema = z.object({
  schema_version: z.string(),
  mode: runtimePolicyModeSchema,
  matrix: z.record(z.string(), z.string()).optional(),
  raw_payload_persisted: z.literal(false).optional(),
}).passthrough();

export type RuntimePolicy = z.infer<typeof runtimePolicySchema>;

export async function fetchRuntimePolicy(): Promise<RuntimePolicy> {
  return runtimePolicySchema.parse(await controlRequest("/runtime-policy", "GET"));
}

export async function setRuntimePolicyMode(mode: RuntimePolicyMode): Promise<RuntimePolicy> {
  return runtimePolicySchema.parse(await controlRequest("/runtime-policy", "POST", { mode }));
}
