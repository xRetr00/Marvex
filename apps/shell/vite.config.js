import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import fs from "fs";
import path from "path";
function readAppVersion() {
    const versionFile = path.resolve(__dirname, "../../version.toml");
    const content = fs.readFileSync(versionFile, "utf8");
    const match = content.match(/^\s*version\s*=\s*"([^"]+)"/m);
    if (!match) {
        throw new Error(`Could not parse app version from ${versionFile}`);
    }
    return match[1];
}
export default defineConfig({
    base: "./",
    plugins: [react(), tailwindcss()],
    define: {
        __MARVEX_APP_VERSION__: JSON.stringify(readAppVersion()),
    },
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
                    if (!id.includes("node_modules"))
                        return undefined;
                    if (id.includes("@react-three"))
                        return "vendor-three-react";
                    if (id.includes("@radix-ui") || id.includes("cmdk"))
                        return "vendor-radix";
                    if (id.includes("framer-motion") || id.includes("motion"))
                        return "vendor-motion";
                    if (id.includes("@melloware") || id.includes("react-lazylog"))
                        return "vendor-logs";
                    if (id.includes("streamdown") ||
                        id.includes("micromark") ||
                        id.includes("remark") ||
                        id.includes("rehype") ||
                        id.includes("unified") ||
                        id.includes("unist") ||
                        id.includes("mdast") ||
                        id.includes("hast") ||
                        id.includes("vfile") ||
                        id.includes("devlop") ||
                        id.includes("decode-named-character-reference") ||
                        id.includes("property-information") ||
                        id.includes("space-separated-tokens") ||
                        id.includes("comma-separated-tokens") ||
                        id.includes("html-url-attributes") ||
                        id.includes("zwitch"))
                        return "vendor-markdown";
                    if (id.includes("lucide-react") || id.includes("@remixicon"))
                        return "vendor-icons";
                    if (id.includes("three/examples"))
                        return "vendor-three-examples";
                    if (id.includes("three/src/renderers"))
                        return "vendor-three-renderers";
                    if (id.includes("three/src/math"))
                        return "vendor-three-math";
                    if (id.includes("three/src/materials"))
                        return "vendor-three-materials";
                    if (id.includes("three/src/geometries"))
                        return "vendor-three-geometries";
                    if (id.includes("three/src/"))
                        return "vendor-three-core";
                    if (id.includes("three"))
                        return "vendor-three";
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
