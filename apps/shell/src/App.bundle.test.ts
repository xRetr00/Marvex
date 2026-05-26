import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf-8");
const viteConfig = readFileSync(resolve(process.cwd(), "vite.config.ts"), "utf-8");

describe("shell route bundle boundaries", () => {
  it("loads top-level surfaces lazily instead of static importing them", () => {
    const staticSurfaceImports = [
      /import\s+\{\s*ChatApp\s*\}\s+from\s+["']\.\/surfaces\/ChatApp["']/,
      /import\s+\{\s*OverlaySurface\s*\}\s+from\s+["']\.\/surfaces\/overlay["']/,
      /import\s+\{\s*ControlLoaderSurface\s*\}\s+from\s+["']\.\/surfaces\/ControlLoader["']/,
      /import\s+\{\s*SetupPage\s*\}\s+from\s+["']\.\/surfaces\/Setup["']/,
    ];

    for (const pattern of staticSurfaceImports) {
      expect(source).not.toMatch(pattern);
    }
  });

  it("builds packaged assets with relative URLs for Tauri resource loading", () => {
    expect(viteConfig).toMatch(/base:\s*["']\.\/["']/);
  });
});
