import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Resolve paths relative to this test file, not process.cwd(), so the suite
// works regardless of which directory Vitest is invoked from (e.g. monorepo root).
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

describe("overlay stylesheet isolation", () => {
  it("keeps Dynamic Island overlay styles out of the main app stylesheet", () => {
    const mainStyles = readFileSync(resolve(repoRoot, "src/styles.css"), "utf-8");
    const overlayStyles = readFileSync(resolve(repoRoot, "src/surfaces/overlay.css"), "utf-8");

    expect(mainStyles).not.toMatch(/overlay-shell|marvex-island|marvex-overlay-document/);
    expect(overlayStyles).toMatch(/overlay-shell/);
    expect(overlayStyles).toMatch(/marvex-overlay-document/);
    expect(overlayStyles).toMatch(/marvex-island-pill/);
  });
});
