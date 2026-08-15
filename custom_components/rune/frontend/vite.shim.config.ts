import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcDir = resolve(__dirname, "src");
const distDir = resolve(__dirname, "dist");

export default defineConfig({
  build: {
    outDir: distDir,
    emptyOutDir: false,
    cssCodeSplit: false,
    rollupOptions: {
      input: resolve(srcDir, "shim.ts"),
      output: {
        entryFileNames: "panel.js",
        assetFileNames: "panel-assets/[name].[ext]",
        format: "iife",
        inlineDynamicImports: true,
      },
    },
    target: "es2022",
  },
});
