import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAgentCatalog, fetchPersonaCatalog, selectActiveAgent, selectActivePersona } from "./controlPlaneClient";
import { controlRequest } from "./shellCommands";

vi.mock("./shellCommands", () => ({
  controlRequest: vi.fn()
}));

const mockedControlRequest = vi.mocked(controlRequest);

describe("agent and persona control plane client", () => {
  beforeEach(() => {
    mockedControlRequest.mockReset();
  });

  it("parses safe agent and persona catalog projections", async () => {
    mockedControlRequest
      .mockResolvedValueOnce({
        schema_version: "1",
        active_agent_id: "agent.main.marvex",
        agent_count: 1,
        selectable_count: 1,
        raw_payload_persisted: false,
        agents: [{
          agent_id: "agent.main.marvex",
          display_name: "Main Marvex",
          role: "orchestrator",
          allowed_intents: [],
          default_capability_refs: [],
          default_skill_refs: [],
          direct_selectable: true,
          can_spawn_subagents: true,
          spawnable_agent_ids: ["agent.deep_search"],
          max_subagents_per_turn: 2,
          raw_prompt_persisted: false
        }]
      })
      .mockResolvedValueOnce({
        schema_version: "1",
        active_persona_id: "persona.marvex.female",
        persona_count: 1,
        raw_payload_persisted: false,
        personas: [{
          persona_id: "persona.marvex.female",
          display_name: "Marvex",
          assistant_identity: "Marvex is the Assistant OS runtime companion.",
          voice_id: "af_heart",
          voice_gender_presentation: "female",
          speaking_style: "Concise and direct.",
          raw_prompt_persisted: false
        }]
      });

    await expect(fetchAgentCatalog()).resolves.toMatchObject({ active_agent_id: "agent.main.marvex" });
    await expect(fetchPersonaCatalog()).resolves.toMatchObject({ active_persona_id: "persona.marvex.female" });
  });

  it("sends non-executing active selection requests", async () => {
    mockedControlRequest
      .mockResolvedValueOnce({
        schema_version: "1",
        active_agent_id: "agent.deep_search",
        agent_count: 1,
        raw_payload_persisted: false,
        execution_started: false,
        agents: [{
          agent_id: "agent.deep_search",
          display_name: "Deep Search",
          role: "specialist",
          allowed_intents: [],
          default_capability_refs: [],
          default_skill_refs: [],
          direct_selectable: true,
          can_spawn_subagents: false,
          spawnable_agent_ids: [],
          max_subagents_per_turn: 0,
          raw_prompt_persisted: false
        }]
      })
      .mockResolvedValueOnce({
        schema_version: "1",
        active_persona_id: "persona.marvex.female",
        persona_count: 1,
        raw_payload_persisted: false,
        execution_started: false,
        personas: [{
          persona_id: "persona.marvex.female",
          display_name: "Marvex",
          assistant_identity: "Marvex is the Assistant OS runtime companion.",
          voice_id: "af_heart",
          voice_gender_presentation: "female",
          speaking_style: "Concise and direct.",
          raw_prompt_persisted: false
        }]
      });

    await selectActiveAgent("agent.deep_search");
    await selectActivePersona("persona.marvex.female");

    expect(mockedControlRequest).toHaveBeenNthCalledWith(1, "/agents/active", "POST", { agent_id: "agent.deep_search" });
    expect(mockedControlRequest).toHaveBeenNthCalledWith(2, "/personas/active", "POST", { persona_id: "persona.marvex.female" });
  });
});
