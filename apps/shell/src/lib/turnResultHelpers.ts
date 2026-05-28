// Synthetic ref id produced by the provider stage when the upstream
// provider returned no real response_id (e.g. on transport error, or for
// adapters that don't surface one). Re-sending these as
// ``previous_response_id`` is useless: the LiteLLM conversation store has
// no entry for them and the LMStudio Responses surface will reject them.
// Filter them out client-side so the chain stays anchored on the last
// *real* response id we received.
export const SYNTHETIC_PROVIDER_REF_SUFFIX = ":provider-turn";

/**
 * Extract a chainable provider response id from a Core turn result.
 *
 * Returns ``undefined`` when:
 * - the result is not an object
 * - the result carries an error envelope (chain should not advance)
 * - no ``provider_turn_refs`` array is present
 * - every candidate ref is missing/empty or matches the synthetic fallback
 *
 * Returns the trimmed ``ref_id`` of the first usable ref otherwise.
 */
export function providerResponseIdFromTurnResult(result: unknown): string | undefined {
  if (!result || typeof result !== "object") return undefined;
  const errorField = (result as { error?: unknown }).error;
  if (errorField !== null && errorField !== undefined) return undefined;
  const refs = (result as { provider_turn_refs?: unknown }).provider_turn_refs;
  if (!Array.isArray(refs)) return undefined;
  for (const ref of refs) {
    if (!ref || typeof ref !== "object") continue;
    const rawRefId = (ref as { ref_id?: unknown }).ref_id;
    if (typeof rawRefId !== "string") continue;
    const refId = rawRefId.trim();
    if (!refId) continue;
    if (refId.endsWith(SYNTHETIC_PROVIDER_REF_SUFFIX)) continue;
    return refId;
  }
  return undefined;
}
