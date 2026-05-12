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
        entryFileNames: "agent-drawer.js",
        chunkFileNames: "agent-drawer-[hash].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith(".css")) {
            return "agent-drawer.css";
          }
          return "agent-drawer-[name][extname]";
        }
      }
    }
  }
});
