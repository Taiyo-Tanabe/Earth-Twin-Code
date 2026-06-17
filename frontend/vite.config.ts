import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      usePolling: true,
      interval: 500,
    },
    proxy: {
      "/api": {
        // Inside Docker: backend service is at backend:8000
        // Outside Docker (local dev): backend is at localhost:8001
        target: process.env.VITE_PROXY_TARGET || "http://backend:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
