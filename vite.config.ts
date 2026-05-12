import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "static/dist",
    emptyOutDir: false,
    sourcemap: false,
    rollupOptions: {
      input: "frontend/agent/main.tsx",
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
