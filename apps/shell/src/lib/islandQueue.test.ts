import { describe, expect, it, vi } from "vitest";
import { createIslandQueue } from "./islandQueue";

describe("island queue", () => {
  it("queues cards, updates the active card in place, and advances after dismiss", () => {
    const queue = createIslandQueue();

    queue.show({ id: "loading", kind: "info", title: "Thinking", autoDismiss: false });
    queue.show({ id: "result", kind: "result", title: "Done", body: "Ready", autoDismiss: false });
    queue.update("loading", { title: "Still thinking" });

    expect(queue.snapshot().active?.title).toBe("Still thinking");
    expect(queue.snapshot().queued).toHaveLength(1);

    queue.dismiss("loading");

    expect(queue.snapshot().active?.id).toBe("result");
    expect(queue.snapshot().queued).toHaveLength(0);
  });

  it("force-preempts the active card and trims queue depth", () => {
    const queue = createIslandQueue({ maxQueue: 1 });

    queue.show({ id: "first", kind: "info", title: "First" });
    queue.show({ id: "second", kind: "info", title: "Second" });
    queue.show({ id: "third", kind: "info", title: "Third" });
    queue.show({ id: "urgent", kind: "info", title: "Urgent" }, { force: true });

    expect(queue.snapshot().active?.id).toBe("urgent");
    expect(queue.snapshot().queued.map((card) => card.id)).toEqual(["third"]);
  });

  it("arms auto-dismiss for cards that should collapse back to idle", () => {
    vi.useFakeTimers();
    const queue = createIslandQueue();

    queue.show({ id: "welcome", kind: "info", title: "Ready", duration: 500 });
    vi.advanceTimersByTime(500);

    expect(queue.snapshot().active).toBeNull();
    vi.useRealTimers();
  });
});
