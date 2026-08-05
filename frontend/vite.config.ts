import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: the Vite server proxies /api to the FastAPI backend (SSE included), so no
// CORS surprises. Prod: FastAPI serves dist/ itself and the proxy is irrelevant.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
