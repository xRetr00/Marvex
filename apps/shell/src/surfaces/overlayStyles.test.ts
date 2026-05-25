import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const repoRoot = process.cwd();

describe("overlay stylesheet isolation", () => {
  it("keeps Dynamic Island overlay styles out of the main app stylesheet", () => {
    const mainStyles = readFileSync(resolve(repoRoot, "src/styles.css"), "utf-8");
    const overlayStyles = readFileSync(resolve(repoRoot, "src/surfaces/overlay.css"), "utf-8");

    expect(mainStyles).not.toMatch(/overlay-shell|marvex-island|marvex-overlay-document/);
    expect(overlayStyles).toMatch(/overlay-shell/);
    expect(overlayStyles).toMatch(/marvex-overlay-document/);
    expect(overlayStyles).toMatch(/marvex-dynamic-island-pill/);
  });
});
