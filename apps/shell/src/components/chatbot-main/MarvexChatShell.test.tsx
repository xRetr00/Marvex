import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MarvexChatShell, type MarvexChatMessage } from "./MarvexChatShell";

const messages: MarvexChatMessage[] = [
  { role: "system", text: "Marvex is ready." },
  { role: "user", text: "Create a plan" },
  { role: "assistant", text: "Here is the plan." },
];

describe("MarvexChatShell", () => {
  afterEach(() => cleanup());

  it("renders Marvex messages with chatbot-main conversation structure", () => {
    render(
      <MarvexChatShell
        messages={messages}
        pending={false}
        onSubmit={vi.fn()}
        renderAssistantOrb={() => <span data-testid="assistant-orb" />}
      />,
    );

    expect(screen.getByRole("log")).toBeInTheDocument();
    expect(screen.getByText("Create a plan")).toBeInTheDocument();
    expect(screen.getByTestId("assistant-orb")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ask anything...")).toBeInTheDocument();
  });

  it("submits text through the Marvex backend callback and keeps composer controls local", async () => {
    const onSubmit = vi.fn();
    const onToggleVoice = vi.fn();
    const onToggleVoiceSession = vi.fn();
    render(
      <MarvexChatShell
        messages={[]}
        pending={false}
        micActive={false}
        onSubmit={onSubmit}
        onToggleVoice={onToggleVoice}
        onToggleVoiceSession={onToggleVoiceSession}
        renderAssistantOrb={() => <span />}
      />,
    );

    await userEvent.type(screen.getByPlaceholderText("Ask anything..."), "Search the workspace");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(onSubmit).toHaveBeenCalledWith("Search the workspace");
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    expect(onToggleVoice).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Start voice mode" }));
    expect(onToggleVoiceSession).toHaveBeenCalledTimes(1);
  });

  it("renders assistant markdown and hides raw approval request internals", () => {
    render(
      <MarvexChatShell
        messages={[
          {
            role: "assistant",
            text: "## Result\n\n- **Done**\n\nApproval required before continuing. approval_request_id=approval-turn-shell-chat-1780301314884",
            approval: {
              approvalId: "approval-turn-shell-chat-1780301314884",
              traceId: "trace-1",
              turnId: "turn-1",
              text: "Open browser",
              status: "pending",
            },
          },
        ]}
        pending={false}
        onSubmit={vi.fn()}
        renderAssistantOrb={() => <span />}
      />,
    );

    expect(screen.getByRole("heading", { name: "Result" })).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.queryByText(/approval-turn-shell-chat/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
  });

  it("renders citation markers as inline citation buttons and keeps one copy action", () => {
    render(
      <MarvexChatShell
        messages={[
          {
            role: "assistant",
            text: "Latest answer [citation 1] and another source [web.evidence.5].",
          },
        ]}
        pending={false}
        onSubmit={vi.fn()}
        renderAssistantOrb={() => <span />}
      />,
    );

    expect(screen.queryByText("[citation 1]")).not.toBeInTheDocument();
    expect(screen.queryByText("[web.evidence.5]")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Citation 1/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Citation 5/i })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /copy/i })).toHaveLength(1);
  });

  it("keeps activity collapsed until the user expands it", async () => {
    render(
      <MarvexChatShell
        messages={[
          {
            role: "assistant",
            text: "Working with trace data.",
            stages: [{ stage_name: "input_normalization", status: "completed" }],
          },
        ]}
        pending={false}
        onSubmit={vi.fn()}
        renderAssistantOrb={() => <span />}
      />,
    );

    expect(screen.getByRole("button", { name: /Activity/i })).toBeInTheDocument();
    expect(screen.queryByText("Input Normalization")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Activity/i }));

    expect(screen.getByText("Input Normalization")).toBeVisible();
    expect(screen.getByText("Step completed.")).toBeVisible();
  });

  it("renders model-authored commentary separately from the final answer", () => {
    render(
      <MarvexChatShell
        messages={[
          {
            role: "assistant",
            text: "MAR.txt contains test data.",
            commentary: ["I'm locating MAR.txt on your Desktop."],
            activity: [{ id: "read-1", name: "file.read", active: false }],
          },
        ]}
        pending={false}
        onSubmit={vi.fn()}
        renderAssistantOrb={() => <span />}
      />,
    );

    expect(screen.getByText("I'm locating MAR.txt on your Desktop.")).toBeInTheDocument();
    expect(screen.getByText("MAR.txt contains test data.")).toBeInTheDocument();
  });

  it("summarizes clarification answers in place with the selected label", async () => {
    const onClarificationAnswer = vi.fn();
    render(
      <MarvexChatShell
        messages={[
          {
            role: "assistant",
            text: "I need one detail.",
            clarification: {
              kind: "single",
              title: "Did you mean OpenAI or open-weight AI models?",
              allowCustom: true,
              originalText: "latest model by open ai",
              options: [
                { id: "openai_company", label: "OpenAI (the company)", description: "ChatGPT, GPT models" },
                { id: "open_weight", label: "Open / open-weight AI models", description: "open-source models" },
              ],
            },
          },
        ]}
        pending={false}
        onSubmit={vi.fn()}
        onClarificationAnswer={onClarificationAnswer}
        renderAssistantOrb={() => <span />}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /OpenAI \(the company\)/ }));
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(onClarificationAnswer).toHaveBeenCalledWith(expect.any(Object), "OpenAI (the company)");
    expect(screen.getByText("Answered: OpenAI (the company)")).toBeInTheDocument();
  });

  it("shows model-aware context and reasoning controls and switches send to stop while generating", async () => {
    const onStop = vi.fn();
    const onSelectReasoningEffort = vi.fn();
    render(
      <MarvexChatShell
        messages={[]}
        pending
        onSubmit={vi.fn()}
        onStop={onStop}
        contextInputTokens={1240}
        outputTokens={320}
        totalTokens={1560}
        reasoningTokens={64}
        contextWindow={128000}
        cachedInputTokens={240}
        reasoningEffort="high"
        reasoningEffortOptions={["low", "medium", "high"]}
        onSelectReasoningEffort={onSelectReasoningEffort}
        renderAssistantOrb={() => <span />}
      />,
    );

    expect(screen.getByRole("button", { name: "Select model" })).toBeInTheDocument();
    expect(screen.getByText("1.2K / 128K")).toHaveAttribute("title", "Input 1240 tokens, output 320, total 1560, 240 cached, 64 reasoning, 128000 context window");
    await userEvent.click(screen.getByRole("button", { name: "Reasoning effort: High" }));
    await userEvent.click(screen.getByRole("button", { name: "Medium" }));
    expect(onSelectReasoningEffort).toHaveBeenCalledWith("medium");
    await userEvent.click(screen.getByRole("button", { name: "Stop generation" }));
    expect(onStop).toHaveBeenCalledTimes(1);
  });
});
