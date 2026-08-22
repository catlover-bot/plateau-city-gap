import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const base = "/plateau-city-gap/";

export default defineConfig({
  base,
  plugins: [react()],
  define: {
    CESIUM_BASE_URL: JSON.stringify(`${base}cesium/`)
  },
  build: {
    chunkSizeWarningLimit: 3_900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/node_modules/react/") || id.includes("/node_modules/react-dom/")) return "react";
          if (id.includes("/node_modules/proj4/")) return "projection";
          return undefined;
        }
      }
    }
  },
  test: {
    include: ["src/**/*.test.ts"]
  }
});
