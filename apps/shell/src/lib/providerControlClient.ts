import { z } from "zod";
import { controlRequest } from "./shellCommands";

export const providerRowSchema = z.object({
  provider_id: z.string(),
  label: z.string().optional(),
  configured: z.boolean().optional(),
  healthy: z.boolean().optional(),
  active_model: z.string().optional(),
  automation_model: z.string().optional(),
  models: z.array(z.string()).optional(),
  model_metadata: z.record(z.string(), z.object({
    context_window: z.number().int().positive().optional(),
    supports_reasoning: z.boolean().optional(),
    supports_reasoning_summary: z.boolean().optional(),
    reasoning_effort_options: z.array(z.string()).optional(),
    reasoning_default: z.string().optional(),
  }).passthrough()).optional(),
  multi_models: z.array(z.string()).optional(),
  base_url: z.string().optional(),
  provider_mode: z.string().optional(),
  supports_custom_base_url: z.boolean().optional(),
  automation_model_capabilities: z.record(z.string(), z.boolean()).optional(),
  automation_policy: z.record(z.string(), z.boolean()).optional(),
  automation_validation: z.object({
    ready: z.boolean(),
    reason_code: z.string().nullable().optional(),
  }).optional(),
  secret_present: z.boolean().optional(),
  secret_display: z.string().optional(),
  secret_value_present: z.literal(false).optional(),
  reasoning_effort: z.string().optional(),
}).passthrough();

export const providerCatalogSchema = z.object({
  schema_version: z.string(),
  active_provider_id: z.string(),
  providers: z.array(providerRowSchema),
  raw_secret_persisted: z.literal(false).optional(),
}).passthrough();

export type ProviderRow = z.infer<typeof providerRowSchema>;
export type ProviderCatalog = z.infer<typeof providerCatalogSchema>;

export async function fetchProviders(): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest("/providers", "GET"));
}

export async function selectProvider(providerId: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest("/providers/active", "POST", { provider_id: providerId }));
}

export async function selectProviderModel(providerId: string, model: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/models/active`, "POST", { model }));
}

export async function selectProviderMultiModels(providerId: string, models: string[]): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/models/multi`, "POST", { models }));
}

export async function selectProviderReasoningEffort(providerId: string, effort: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/reasoning`, "POST", { effort }));
}

export async function setProviderConnection(providerId: string, baseUrl: string, providerMode: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/connection`, "POST", { base_url: baseUrl, provider_mode: providerMode }));
}

export async function selectProviderAutomationModel(
  providerId: string,
  model: string,
  options: { supportsVision?: boolean; visionRequired?: boolean } = {},
): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/automation`, "POST", {
    model,
    supports_vision: options.supportsVision,
    vision_required: options.visionRequired,
  }));
}

export async function refreshProviderModels(providerId: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/models/refresh`, "POST"));
}

export async function setProviderSecret(providerId: string, secret: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/secret`, "POST", { secret }));
}

export async function removeProviderSecret(providerId: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/secret`, "DELETE"));
}
