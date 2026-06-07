import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadMemorySettings } from "@/lib/memorySettings";

const controlRequest = vi.fn(async () => ({
  enabled: true,
  graph: { ready: true, backend: "graphiti", provider: "falkordb" },
  vector: { ready: true, backend: "qdrant", collection_name: "marvex_memory" },
}));

vi.mock("@/lib/shellCommands", () => ({
  controlRequest,
}));

afterEach(() => {
  cleanup();
  localStorage.clear();
  controlRequest.mockClear();
});

describe("MemorySettings", () => {
  it("renders local memory controls and backend health", async () => {
    const { MemorySettings } = await import("./MemorySettings");

    render(<MemorySettings />);

    expect(screen.getByRole("heading", { name: "Memories" })).toBeInTheDocument();
    expect(screen.getByLabelText("Memory backend")).toHaveValue("graphiti_qdrant");
    expect(screen.getByLabelText("Graphiti provider")).toHaveValue("falkordb");
    expect(screen.getByLabelText("Graphiti LLM provider")).toHaveValue("lm_studio");
    expect(screen.getByLabelText("Graphiti LLM client")).toHaveValue("openai_generic");
    expect(screen.getByLabelText("Graphiti model")).toHaveValue("google/gemma-4-e2b");
    expect(screen.getByLabelText("FalkorDB host")).toHaveValue("127.0.0.1");
    expect(screen.getByLabelText("FalkorDB port")).toHaveValue(6379);
    expect(screen.getByLabelText("Qdrant collection")).toHaveValue("marvex_memory");
    expect(screen.getByText("retrieval")).toBeInTheDocument();
    expect(screen.getByText("context injection")).toBeInTheDocument();

    await waitFor(() => expect(controlRequest).toHaveBeenCalledWith("/memory/health", "GET"));
    expect(await screen.findByText("graph.backend")).toBeInTheDocument();
    expect(screen.getByText("vector.collection_name")).toBeInTheDocument();
  });

  it("saves Graphiti model and FalkorDB endpoint edits in shell settings", async () => {
    const { MemorySettings } = await import("./MemorySettings");

    render(<MemorySettings />);

    await userEvent.clear(screen.getByLabelText("Graphiti model"));
    await userEvent.type(screen.getByLabelText("Graphiti model"), "local/memory-model");
    await userEvent.clear(screen.getByLabelText("FalkorDB host"));
    await userEvent.type(screen.getByLabelText("FalkorDB host"), "192.168.1.40");
    await userEvent.clear(screen.getByLabelText("FalkorDB port"));
    await userEvent.type(screen.getByLabelText("FalkorDB port"), "6380");
    await userEvent.click(screen.getByRole("button", { name: "Save memory settings" }));

    const settings = loadMemorySettings();
    expect(settings.llmModel).toBe("local/memory-model");
    expect(settings.falkorHost).toBe("192.168.1.40");
    expect(settings.falkorPort).toBe(6380);
  });
});
