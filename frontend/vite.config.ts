import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
  },
  test: {
    environment: "jsdom",
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    setupFiles: "./src/setupTests.ts",
    globals: true,
  },
});
