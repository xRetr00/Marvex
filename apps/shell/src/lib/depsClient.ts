import { z } from "zod";
import { controlRequest } from "./shellCommands";

export const depSchema = z.object({
  id: z.string(),
  label: z.string(),
  group: z.string(),
  installed: z.boolean(),
  feature: z.string(),
});

export const depsResponseSchema = z.object({
  deps: z.array(depSchema),
  features: z.object({
    tts: z.boolean(),
    stt: z.boolean(),
    wakeword: z.boolean(),
    web_search: z.boolean(),
    browser: z.boolean(),
    embeddings: z.boolean(),
  }),
});

export type Dep = z.infer<typeof depSchema>;
export type DepsResponse = z.infer<typeof depsResponseSchema>;

export async function fetchDeps(): Promise<DepsResponse> {
  const raw = await controlRequest("/deps");
  return depsResponseSchema.parse(raw);
}

export async function installDep(id: string): Promise<{ id: string; status: "installing" | "installed" | "error"; detail?: string }> {
  const raw = await controlRequest("/deps/install", "POST", { id });
  const parsed = z.object({
    id: z.string(),
    status: z.enum(["installing", "installed", "error"]),
    detail: z.string().optional(),
  }).parse(raw);
  return parsed;
}
