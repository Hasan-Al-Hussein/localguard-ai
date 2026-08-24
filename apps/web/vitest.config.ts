import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
      "@localguard/contracts": fileURLToPath(new URL("../../packages/contracts/src/index.ts", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    setupFiles: ["./test/dom.ts", "./test/setup.ts"],
    include: ["test/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
