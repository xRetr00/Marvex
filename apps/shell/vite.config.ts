import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: false
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("@react-three")) return "vendor-three-react";
          if (id.includes("three/examples")) return "vendor-three-examples";
          if (id.includes("three/src/renderers")) return "vendor-three-renderers";
          if (id.includes("three/src/math")) return "vendor-three-math";
          if (id.includes("three/src/materials")) return "vendor-three-materials";
          if (id.includes("three/src/geometries")) return "vendor-three-geometries";
          if (id.includes("three/src/")) return "vendor-three-core";
          if (id.includes("three")) return "vendor-three";
          return "vendor";
        }
      }
    }
  },
  clearScreen: false,
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts"
  }
});
