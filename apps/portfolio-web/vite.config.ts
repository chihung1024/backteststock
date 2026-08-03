import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  root: resolve(__dirname),
  base: "/portfolio/",
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, "../../public/portfolio"),
    emptyOutDir: true,
    sourcemap: true,
    target: "es2022",
    assetsDir: "assets",
  },
});
