import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Resolve paths relative to this test file so the suite works when Vitest is
// run from the monorepo root rather than apps/shell directly.
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

describe("single Dynamic Island overlay", () => {
  it("does not keep the old Spotlight route, commands, or Tauri window", () => {
    const appTsx = readFileSync(resolve(repoRoot, "src/App.tsx"), "utf-8");
    const commands = readFileSync(resolve(repoRoot, "src/lib/shellCommands.ts"), "utf-8");
    const tauriConfig = readFileSync(resolve(repoRoot, "src-tauri/tauri.conf.json"), "utf-8");
    const rust = readFileSync(resolve(repoRoot, "src-tauri/src/lib.rs"), "utf-8");

    expect(appTsx).not.toMatch(/Spotlight|spotlight/);
    expect(commands).not.toMatch(/showSpotlight|hideSpotlight|spotlight/);
    expect(tauriConfig).not.toMatch(/spotlight/i);
    expect(rust).not.toMatch(/show_spotlight|hide_spotlight|position_spotlight|spotlight/i);
  });
});
