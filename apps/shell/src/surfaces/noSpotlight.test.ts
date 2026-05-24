import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const repoRoot = process.cwd();

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
