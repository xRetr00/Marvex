import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { WorkTrace } from "./work-trace";

describe("WorkTrace", () => {
  afterEach(cleanup);

  it("shows the current shimmering step while working", () => {
    render(
      <WorkTrace
        streaming
        startedAt={Date.now()}
        activity={[{ id: "1", name: "file.read", arguments: '{"path":"docs/notes.txt"}', active: true }]}
      />,
    );
    // Header reflects the live step (present-continuous + target basename).
    expect(screen.getByText("Reading notes.txt")).toBeInTheDocument();
  });

  it("falls back to a Thinking label while only reasoning is streaming", () => {
    render(<WorkTrace streaming startedAt={Date.now()} thinkingStreaming thinking="" activity={[]} />);
    expect(screen.getByText("Thinking")).toBeInTheDocument();
  });

  it("opens reasoning details by default when provider reasoning text exists", () => {
    render(<WorkTrace streaming={false} startedAt={0} endedAt={1000} thinking="Plan the next tool call." activity={[]} />);
    expect(screen.getByText("Plan the next tool call.")).toBeInTheDocument();
  });

  it("renders a 'Worked for' summary with the elapsed duration when done", () => {
    render(
      <WorkTrace
        streaming={false}
        startedAt={0}
        endedAt={5000}
        activity={[{ id: "1", name: "file.read", arguments: "{}", active: false }]}
      />,
    );
    expect(screen.getByText("Worked for 5s")).toBeInTheDocument();
  });

  it("reveals the steps when the trace is expanded", async () => {
    render(
      <WorkTrace
        streaming={false}
        startedAt={0}
        endedAt={62000}
        activity={[{ id: "1", name: "web.search", arguments: '{"query":"open source"}', active: false }]}
      />,
    );
    // Minutes+seconds formatting.
    expect(screen.getByText("Worked for 1m 2s")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText("Searched the web open source")).toBeInTheDocument();
  });
});
