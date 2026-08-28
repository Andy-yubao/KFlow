import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

/// <reference types="vitest/config" />

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "KFLOW_");
  const apiTarget = env.KFLOW_API_TARGET || "http://127.0.0.1:8765";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": apiTarget,
      },
    },
    build: {
      outDir: "../kflow/human/static",
      emptyOutDir: true,
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      fileParallelism: false,
      maxWorkers: 1,
    },
  };
});
