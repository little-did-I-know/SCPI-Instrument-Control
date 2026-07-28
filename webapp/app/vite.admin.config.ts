import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

// A separate config, and a separate outDir, so the admin bundle never lands in
// the main app's static directory -- whose SPA catch-all would serve it to any
// LAN browser that asked.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@design": resolve(__dirname, "../design") } },
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8766", changeOrigin: true } },
  },
  build: {
    outDir: "dist-admin",
    emptyOutDir: true,
    rollupOptions: { input: resolve(__dirname, "admin.html") },
  },
});
