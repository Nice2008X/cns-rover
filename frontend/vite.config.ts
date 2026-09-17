import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../cns_car/web", emptyOutDir: true },
  server: { proxy: { "/api": { target: "http://127.0.0.1:8765", ws: true } } },
});
