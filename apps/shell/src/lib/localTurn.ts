export function finalTextFromTurnResult(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "No response payload returned.";
  const result = payload as { assistant_final_response?: { text?: unknown }; error?: { message?: unknown } };
  const text = result.assistant_final_response?.text;
  if (typeof text === "string" && text.trim()) return text;
  const error = result.error?.message;
  if (typeof error === "string" && error.trim()) return error;
  return "No displayable response returned.";
}

export interface TurnStage {
  stage_name: string;
  status: string;
}

/** Model-driven UI directive emitted by the backend (show_product/info/image/plan). */
export interface UiDirective {
  kind: "product" | "info" | "image" | "plan";
  [key: string]: unknown;
}

export interface CitationRef {
  id: string;
  title?: string;
  url?: string;
  domain?: string;
  snippet?: string;
  sourceType?: string;
  sourceId?: string;
  validAt?: string;
  invalidAt?: string;
}

/** Read backend UI directives from assistant_final_response.metadata.ui_directives. */
export function uiDirectivesFromTurnResult(payload: unknown): UiDirective[] {
  if (!payload || typeof payload !== "object") return [];
  const final = (payload as { assistant_final_response?: { metadata?: unknown } }).assistant_final_response;
  const metadata = final?.metadata;
  if (!metadata || typeof metadata !== "object") return [];
  const directives = (metadata as { ui_directives?: unknown }).ui_directives;
  if (!Array.isArray(directives)) return [];
  return directives.filter(
    (d): d is UiDirective =>
      Boolean(d) && typeof d === "object" && ["product", "info", "image", "plan"].includes((d as { kind?: string }).kind ?? ""),
  );
}

/** Extract the per-stage reasoning trace from a turn result (drives chain-of-thought). */
export function stagesFromTurnResult(payload: unknown): TurnStage[] {
  if (!payload || typeof payload !== "object") return [];
  const summaries = (payload as { stage_summaries?: unknown }).stage_summaries;
  if (!Array.isArray(summaries)) return [];
  return summaries
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null;
      const stage = entry as { stage_name?: unknown; status?: unknown };
      if (typeof stage.stage_name !== "string") return null;
      return { stage_name: stage.stage_name, status: typeof stage.status === "string" ? stage.status : "completed" };
    })
    .filter((s): s is TurnStage => s !== null);
}

export function citationsFromTurnResult(payload: unknown): CitationRef[] {
  if (!payload || typeof payload !== "object") return [];
  const resultMetadata = (payload as { metadata?: unknown }).metadata;
  const finalMetadata = (payload as { assistant_final_response?: { metadata?: unknown } }).assistant_final_response?.metadata;
  const refs: CitationRef[] = [];
  for (const metadata of [resultMetadata, finalMetadata]) {
    if (!metadata || typeof metadata !== "object") continue;
    const grounding = (metadata as { grounding?: unknown }).grounding;
    const webRefs = grounding && typeof grounding === "object" ? (grounding as { evidence_refs?: unknown; web_evidence_refs?: unknown }).evidence_refs ?? (grounding as { web_evidence_refs?: unknown }).web_evidence_refs : undefined;
    const memoryRefs = grounding && typeof grounding === "object" ? (grounding as { memory_evidence_refs?: unknown }).memory_evidence_refs : undefined;
    for (const entry of [...(Array.isArray(webRefs) ? webRefs : []), ...(Array.isArray(memoryRefs) ? memoryRefs : [])]) {
      if (!entry || typeof entry !== "object") continue;
      const ref = entry as { evidence_id?: unknown; citation_id?: unknown; source_url?: unknown; url?: unknown; uri?: unknown; title?: unknown; domain?: unknown; snippet?: unknown; quote_preview?: unknown; source_type?: unknown; source_id?: unknown; valid_at?: unknown; invalid_at?: unknown };
      const id = typeof ref.evidence_id === "string" ? ref.evidence_id : typeof ref.citation_id === "string" ? ref.citation_id : "";
      if (!id) continue;
      refs.push({
        id,
        url: typeof ref.source_url === "string" ? ref.source_url : typeof ref.url === "string" ? ref.url : typeof ref.uri === "string" ? ref.uri : undefined,
        title: typeof ref.title === "string" ? ref.title : undefined,
        domain: typeof ref.domain === "string" ? ref.domain : undefined,
        snippet: typeof ref.snippet === "string" ? ref.snippet : typeof ref.quote_preview === "string" ? ref.quote_preview : undefined,
        sourceType: typeof ref.source_type === "string" ? ref.source_type : undefined,
        sourceId: typeof ref.source_id === "string" ? ref.source_id : undefined,
        validAt: typeof ref.valid_at === "string" ? ref.valid_at : undefined,
        invalidAt: typeof ref.invalid_at === "string" ? ref.invalid_at : undefined,
      });
    }
  }
  return Array.from(new Map(refs.map((ref) => [ref.id, ref])).values());
}
