import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@design": resolve(__dirname, "../design") } },
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8765", ws: true, changeOrigin: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
