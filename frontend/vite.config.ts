import react from "@vitejs/plugin-react";
import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";

// Vite's dev server refuses to let the browser import .mjs files that live in /public
// (onnxruntime-web does exactly that for the voice detector). This plugin serves /vad/* files
// as plain static files BEFORE Vite's transform step, so the microphone voice detection can load.
const MIME: Record<string, string> = {
  ".mjs": "text/javascript",
  ".js": "text/javascript",
  ".wasm": "application/wasm",
  ".onnx": "application/octet-stream",
};

function serveVadRaw(): Plugin {
  const dir = fileURLToPath(new URL("./public/vad", import.meta.url));
  return {
    name: "serve-vad-raw",
    configureServer(server) {
      server.middlewares.use("/vad", (req, res, next) => {
        const name = decodeURIComponent((req.url ?? "").split("?")[0]).replace(/^[/\\]+/, "");
        const file = join(dir, name);
        if (!name || name.includes("..") || !existsSync(file) || !statSync(file).isFile()) return next();
        res.setHeader("Content-Type", MIME[extname(file)] ?? "application/octet-stream");
        res.setHeader("Cache-Control", "no-cache");
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), serveVadRaw()],
  server: { port: 5173 },
  build: { chunkSizeWarningLimit: 1500 },
});
