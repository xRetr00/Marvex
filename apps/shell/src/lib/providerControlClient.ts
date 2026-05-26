import { z } from "zod";
import { controlRequest } from "./shellCommands";

export const providerRowSchema = z.object({
  provider_id: z.string(),
  label: z.string().optional(),
  configured: z.boolean().optional(),
  healthy: z.boolean().optional(),
  active_model: z.string().optional(),
  models: z.array(z.string()).optional(),
  multi_models: z.array(z.string()).optional(),
  secret_present: z.boolean().optional(),
  secret_display: z.string().optional(),
  secret_value_present: z.literal(false).optional(),
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

export async function refreshProviderModels(providerId: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/models/refresh`, "POST"));
}

export async function setProviderSecret(providerId: string, secret: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/secret`, "POST", { secret }));
}

export async function removeProviderSecret(providerId: string): Promise<ProviderCatalog> {
  return providerCatalogSchema.parse(await controlRequest(`/providers/${encodeURIComponent(providerId)}/secret`, "DELETE"));
}
