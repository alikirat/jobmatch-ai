/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Proxies API calls to the backend during `npm run dev` so the frontend can use
    // plain relative fetch URLs (e.g. `/jobs/queue`) with no CORS setup required.
    proxy: {
      "/jobs": "http://localhost:8000",
      "/score": "http://localhost:8000",
      "/resumes": "http://localhost:8000",
      "/ingest": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./vitest.setup.ts",
  },
});
