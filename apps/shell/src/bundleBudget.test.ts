import { existsSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const assetsDir = resolve(process.cwd(), "dist/assets");
const maxChunkBytes = 500 * 1024;

describe("shell production bundle budget", () => {
  it.runIf(existsSync(assetsDir))("keeps every generated JavaScript chunk under 500 kB", () => {
    const oversized = readdirSync(assetsDir)
      .filter((name) => name.endsWith(".js"))
      .map((name) => {
        const size = statSync(resolve(assetsDir, name)).size;
        return { name, size };
      })
      .filter((chunk) => chunk.size > maxChunkBytes);

    expect(oversized).toEqual([]);
  });
});
