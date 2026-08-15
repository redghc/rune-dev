import { defineConfig, type Plugin } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { rename } from "node:fs/promises";
import { existsSync } from "node:fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcDir = resolve(__dirname, "src");
const distDir = resolve(__dirname, "dist");

// Vite always emits the SPA entry as ``index.html`` (it insists on a
// stable filename for the HTML plugin). The Python loader expects
// ``panel.html``, so we rename at the end of the bundle hook.
const renameIndexToPanel = (): Plugin => ({
  name: "rune-rename-spa-output",
  async closeBundle() {
    const src = resolve(distDir, "index.html");
    const dst = resolve(distDir, "panel.html");
    if (existsSync(src)) await rename(src, dst);
  },
});

export default defineConfig({
  root: srcDir,
  plugins: [viteSingleFile(), renameIndexToPanel()],
  build: {
    outDir: distDir,
    emptyOutDir: false,
    cssCodeSplit: false,
    assetsInlineLimit: 100_000_000,
    rollupOptions: {
      input: resolve(srcDir, "index.html"),
      output: {
        entryFileNames: "[name].js",
        inlineDynamicImports: true,
      },
    },
  },
});
