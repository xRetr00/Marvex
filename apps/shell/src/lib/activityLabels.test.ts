import { describe, expect, it } from "vitest";

import { activityLabel } from "./activityLabels";

describe("activityLabel", () => {
  it("uses present-continuous while active and past tense when done", () => {
    const base = { id: "1", name: "file.search", arguments: '{"query":"model picker"}' };
    expect(activityLabel({ ...base, active: true })).toBe("Searching model picker");
    expect(activityLabel({ ...base, active: false })).toBe("Searched model picker");
  });

  it("shows the basename for path targets", () => {
    expect(
      activityLabel({ id: "2", name: "file.read", arguments: '{"path":"apps/shell/src/ContextMenu.tsx"}', active: false })
    ).toBe("Read ContextMenu.tsx");
  });

  it("maps grep and patch verbs", () => {
    expect(activityLabel({ id: "3", name: "file.rg", arguments: '{"name":"Choose a model"}', active: false })).toBe("Grepped Choose a model");
    expect(activityLabel({ id: "4", name: "file.patch", arguments: '{"path":"a/b.py"}', active: true })).toBe("Patching b.py");
  });

  it("tolerates underscore tool names from weak models", () => {
    expect(activityLabel({ id: "5", name: "file_write", arguments: '{"path":"notes.txt"}', active: true })).toBe("Editing notes.txt");
  });

  it("falls back gracefully for unknown tools and bad json", () => {
    expect(activityLabel({ id: "6", name: "mystery.tool", arguments: "not json", active: true })).toBe("Running mystery tool");
    expect(activityLabel({ id: "7", name: "web.search", active: true })).toBe("Searching the web");
  });
});
