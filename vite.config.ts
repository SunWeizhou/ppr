import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  build: {
    outDir: "static/dist",
    emptyOutDir: false,
    sourcemap: false,
    rollupOptions: {
      input: "frontend/agent-panel/index.tsx",
      output: {
        entryFileNames: "agent-panel.js",
        chunkFileNames: "agent-panel-[hash].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith(".css")) {
            return "agent-panel.css";
          }
          return "agent-panel-[name][extname]";
        }
      }
    }
  }
});
