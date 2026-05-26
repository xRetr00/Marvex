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
    render(
      <MarvexChatShell
        messages={[]}
        pending={false}
        micActive={false}
        onSubmit={onSubmit}
        onToggleVoice={onToggleVoice}
        renderAssistantOrb={() => <span />}
      />,
    );

    await userEvent.type(screen.getByPlaceholderText("Ask anything..."), "Search the workspace");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(onSubmit).toHaveBeenCalledWith("Search the workspace");
    await userEvent.click(screen.getByRole("button", { name: "Start voice capture" }));
    expect(onToggleVoice).toHaveBeenCalledTimes(1);
  });
});
