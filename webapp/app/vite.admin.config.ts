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
    // changeOrigin rewrites Host so the gateway's TrustedHost allowlist is
    // satisfied; headers.Origin does the same for its Origin allowlist, which
    // otherwise sees this dev server (localhost:5173) and refuses every write.
    // Rewrite it here rather than relaxing the check in the app: the whole
    // point of that check is that it does not have a hole for convenience.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8766",
        changeOrigin: true,
        headers: { Origin: "http://127.0.0.1:8766" },
      },
    },
  },
  build: {
    outDir: "dist-admin",
    emptyOutDir: true,
    rollupOptions: { input: resolve(__dirname, "admin.html") },
  },
});
