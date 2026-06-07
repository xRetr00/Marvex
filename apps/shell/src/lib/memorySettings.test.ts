import { afterEach, describe, expect, it } from "vitest";
import { defaultMemorySettings, loadMemorySettings, memorySettingsEnv, saveMemorySettings } from "./memorySettings";

afterEach(() => {
  localStorage.clear();
});

describe("memorySettings", () => {
  it("defaults to local Graphiti, FalkorDB, Qdrant, and LM Studio", () => {
    const settings = loadMemorySettings();

    expect(settings.backend).toBe("graphiti_qdrant");
    expect(settings.llmClientKind).toBe("openai_generic");
    expect(settings.llmProvider).toBe("lm_studio");
    expect(settings.llmBaseUrl).toBe("http://127.0.0.1:1234/v1");
    expect(settings.llmModel).toBe("google/gemma-4-e2b");
    expect(settings.embeddingModel).toBe("text-embedding-nomic-embed-text-v1.5");
    expect(settings.embeddingDimension).toBe(768);
    expect(settings.falkorHost).toBe("127.0.0.1");
    expect(settings.falkorPort).toBe(6379);
    expect(settings.qdrantCollection).toBe("marvex_memory");
  });

  it("persists editable connection settings without dropping defaults", () => {
    saveMemorySettings({
      ...defaultMemorySettings,
      falkorHost: "192.168.1.40",
      falkorPort: 6380,
      llmModel: "local/custom-memory-model",
    });

    const settings = loadMemorySettings();

    expect(settings.falkorHost).toBe("192.168.1.40");
    expect(settings.falkorPort).toBe(6380);
    expect(settings.llmModel).toBe("local/custom-memory-model");
    expect(settings.graphitiProvider).toBe(defaultMemorySettings.graphitiProvider);
  });

  it("renders a secret-safe environment preview", () => {
    const preview = memorySettingsEnv({
      ...defaultMemorySettings,
      llmApiKeyPresent: true,
      embeddingApiKeyPresent: true,
    });

    expect(preview).toContain("MARVEX_MEMORY_BACKEND=graphiti_qdrant");
    expect(preview).toContain("MARVEX_MEMORY_FALKOR_HOST=127.0.0.1");
    expect(preview).toContain("MARVEX_MEMORY_LLM_CLIENT_KIND=openai_generic");
    expect(preview).toContain("MARVEX_MEMORY_LLM_API_KEY=<saved>");
    expect(preview).not.toContain("sk-");
  });
});
