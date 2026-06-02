import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  // Temporarily off so production errors show real function names (debugging the white screen)
  build: { minify: false, sourcemap: true },
});
