import { describe, expect, it } from "vitest";
import { citationsFromTurnResult } from "./localTurn";

describe("citationsFromTurnResult memory evidence", () => {
  it("extracts memory source attribution from grounding metadata", () => {
    const citations = citationsFromTurnResult({
      assistant_final_response: {
        metadata: {
          grounding: {
            memory_evidence_refs: [
              {
                evidence_id: "memory.evidence.graph.fact.codename",
                title: "Graphiti temporal fact",
                domain: "memory",
                uri: "graphiti://graph.fact.codename",
                quote_preview: "User prefers Cedar as the project codename.",
                source_type: "synthesis",
                source_id: "graph.fact.codename",
                valid_at: "2026-06-07T00:00:00+00:00",
              },
            ],
          },
        },
      },
    });

    expect(citations).toEqual([
      {
        id: "memory.evidence.graph.fact.codename",
        url: "graphiti://graph.fact.codename",
        title: "Graphiti temporal fact",
        domain: "memory",
        snippet: "User prefers Cedar as the project codename.",
        sourceType: "synthesis",
        sourceId: "graph.fact.codename",
        validAt: "2026-06-07T00:00:00+00:00",
        invalidAt: undefined,
      },
    ]);
  });
});
