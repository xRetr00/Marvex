export type MemoryBackend = "graphiti_qdrant" | "disabled";
export type GraphitiProvider = "falkordb" | "neo4j";
export type MemoryLlmProvider = "lm_studio" | "openai" | "custom_openai_compatible";
export type MemoryLlmClientKind = "openai_generic" | "openai_responses";

export type MemorySettings = {
  backend: MemoryBackend;
  namespace: string;
  graphRequired: boolean;
  vectorRequired: boolean;
  graphitiProvider: GraphitiProvider;
  llmProvider: MemoryLlmProvider;
  llmClientKind: MemoryLlmClientKind;
  llmBaseUrl: string;
  llmModel: string;
  llmSmallModel: string;
  llmApiKeyPresent: boolean;
  embeddingBaseUrl: string;
  embeddingModel: string;
  embeddingDimension: number;
  embeddingApiKeyPresent: boolean;
  rerankerBaseUrl: string;
  rerankerModel: string;
  falkorHost: string;
  falkorPort: number;
  falkorUsername: string;
  falkorPasswordPresent: boolean;
  qdrantPath: string;
  qdrantCollection: string;
  qdrantEmbeddingModel: string;
  retrievalLimit: number;
  contextTokenBudget: number;
  sourceAttributionRequired: boolean;
  userControlsEnabled: boolean;
};

const STORAGE_KEY = "marvex.memory.settings.v1";

export const defaultMemorySettings: MemorySettings = {
  backend: "graphiti_qdrant",
  namespace: "marvex",
  graphRequired: true,
  vectorRequired: true,
  graphitiProvider: "falkordb",
  llmProvider: "lm_studio",
  llmClientKind: "openai_generic",
  llmBaseUrl: "http://127.0.0.1:1234/v1",
  llmModel: "google/gemma-4-e2b",
  llmSmallModel: "google/gemma-4-e2b",
  llmApiKeyPresent: false,
  embeddingBaseUrl: "http://127.0.0.1:1234/v1",
  embeddingModel: "text-embedding-nomic-embed-text-v1.5",
  embeddingDimension: 768,
  embeddingApiKeyPresent: false,
  rerankerBaseUrl: "http://127.0.0.1:1234/v1",
  rerankerModel: "",
  falkorHost: "127.0.0.1",
  falkorPort: 6379,
  falkorUsername: "",
  falkorPasswordPresent: false,
  qdrantPath: ".marvex-memory/qdrant",
  qdrantCollection: "marvex_memory",
  qdrantEmbeddingModel: "BAAI/bge-small-en-v1.5",
  retrievalLimit: 8,
  contextTokenBudget: 1800,
  sourceAttributionRequired: true,
  userControlsEnabled: true,
};

export function loadMemorySettings(): MemorySettings {
  if (typeof localStorage === "undefined") return { ...defaultMemorySettings };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...defaultMemorySettings };
    return normalizeMemorySettings(JSON.parse(raw));
  } catch {
    return { ...defaultMemorySettings };
  }
}

export function saveMemorySettings(settings: MemorySettings): MemorySettings {
  const normalized = normalizeMemorySettings(settings);
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  }
  return normalized;
}

export function resetMemorySettings(): MemorySettings {
  if (typeof localStorage !== "undefined") localStorage.removeItem(STORAGE_KEY);
  return { ...defaultMemorySettings };
}

export function memorySettingsEnv(settings: MemorySettings): string {
  const lines = [
    `MARVEX_MEMORY_BACKEND=${settings.backend}`,
    `MARVEX_MEMORY_NAMESPACE=${settings.namespace}`,
    `MARVEX_MEMORY_GRAPH_REQUIRED=${settings.graphRequired ? "1" : "0"}`,
    `MARVEX_MEMORY_VECTOR_REQUIRED=${settings.vectorRequired ? "1" : "0"}`,
    `MARVEX_MEMORY_FALKOR_HOST=${settings.falkorHost}`,
    `MARVEX_MEMORY_FALKOR_PORT=${settings.falkorPort}`,
    `MARVEX_MEMORY_FALKOR_USERNAME=${settings.falkorUsername}`,
    `MARVEX_MEMORY_FALKOR_PASSWORD=${settings.falkorPasswordPresent ? "<saved>" : ""}`,
    `MARVEX_MEMORY_LLM_CLIENT_KIND=${settings.llmClientKind}`,
    `MARVEX_MEMORY_LLM_BASE_URL=${settings.llmBaseUrl}`,
    `MARVEX_MEMORY_LLM_MODEL=${settings.llmModel}`,
    `MARVEX_MEMORY_LLM_SMALL_MODEL=${settings.llmSmallModel}`,
    `MARVEX_MEMORY_LLM_API_KEY=${settings.llmApiKeyPresent ? "<saved>" : ""}`,
    `MARVEX_MEMORY_EMBEDDING_BASE_URL=${settings.embeddingBaseUrl}`,
    `MARVEX_MEMORY_EMBEDDING_MODEL=${settings.embeddingModel}`,
    `MARVEX_MEMORY_EMBEDDING_DIMENSION=${settings.embeddingDimension}`,
    `MARVEX_MEMORY_EMBEDDING_API_KEY=${settings.embeddingApiKeyPresent ? "<saved>" : ""}`,
    `MARVEX_MEMORY_RERANKER_BASE_URL=${settings.rerankerBaseUrl}`,
    `MARVEX_MEMORY_RERANKER_MODEL=${settings.rerankerModel}`,
    `MARVEX_MEMORY_QDRANT_PATH=${settings.qdrantPath}`,
    `MARVEX_MEMORY_QDRANT_COLLECTION=${settings.qdrantCollection}`,
    `MARVEX_MEMORY_QDRANT_EMBEDDING_MODEL=${settings.qdrantEmbeddingModel}`,
    `MARVEX_MEMORY_RETRIEVAL_LIMIT=${settings.retrievalLimit}`,
    `MARVEX_MEMORY_CONTEXT_TOKEN_BUDGET=${settings.contextTokenBudget}`,
    `MARVEX_MEMORY_SOURCE_ATTRIBUTION_REQUIRED=${settings.sourceAttributionRequired ? "1" : "0"}`,
    `MARVEX_MEMORY_USER_CONTROLS_ENABLED=${settings.userControlsEnabled ? "1" : "0"}`,
  ];
  return lines.join("\n");
}

function normalizeMemorySettings(value: unknown): MemorySettings {
  const raw = value && typeof value === "object" ? value as Partial<MemorySettings> : {};
  return {
    ...defaultMemorySettings,
    ...raw,
    backend: raw.backend === "disabled" ? "disabled" : "graphiti_qdrant",
    graphitiProvider: raw.graphitiProvider === "neo4j" ? "neo4j" : "falkordb",
    llmProvider: normalizeLlmProvider(raw.llmProvider),
    llmClientKind: raw.llmClientKind === "openai_responses" ? "openai_responses" : "openai_generic",
    embeddingDimension: positiveInteger(raw.embeddingDimension, defaultMemorySettings.embeddingDimension),
    falkorPort: positiveInteger(raw.falkorPort, defaultMemorySettings.falkorPort),
    retrievalLimit: positiveInteger(raw.retrievalLimit, defaultMemorySettings.retrievalLimit),
    contextTokenBudget: positiveInteger(raw.contextTokenBudget, defaultMemorySettings.contextTokenBudget),
    graphRequired: Boolean(raw.graphRequired ?? defaultMemorySettings.graphRequired),
    vectorRequired: Boolean(raw.vectorRequired ?? defaultMemorySettings.vectorRequired),
    llmApiKeyPresent: Boolean(raw.llmApiKeyPresent),
    embeddingApiKeyPresent: Boolean(raw.embeddingApiKeyPresent),
    falkorPasswordPresent: Boolean(raw.falkorPasswordPresent),
    sourceAttributionRequired: Boolean(raw.sourceAttributionRequired ?? defaultMemorySettings.sourceAttributionRequired),
    userControlsEnabled: Boolean(raw.userControlsEnabled ?? defaultMemorySettings.userControlsEnabled),
  };
}

function normalizeLlmProvider(value: unknown): MemoryLlmProvider {
  if (value === "openai" || value === "custom_openai_compatible") return value;
  return "lm_studio";
}

function positiveInteger(value: unknown, fallback: number): number {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isInteger(number) && number > 0 ? number : fallback;
}
