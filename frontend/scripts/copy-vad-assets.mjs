// Copies the VAD worklet, Silero models and ONNX runtime WASM into public/vad so nothing is loaded from a CDN.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const out = join("public", "vad");
mkdirSync(out, { recursive: true });
const vad = join("node_modules", "@ricky0123", "vad-web", "dist");
const ort = join("node_modules", "onnxruntime-web", "dist");
const files = [
  [vad, "vad.worklet.bundle.min.js"],
  [vad, "silero_vad_v5.onnx"],
  [vad, "silero_vad_legacy.onnx"],
  [ort, "ort-wasm-simd-threaded.mjs"],
  [ort, "ort-wasm-simd-threaded.wasm"],
];
for (const [dir, name] of files) {
  const src = join(dir, name);
  if (!existsSync(src)) {
    console.error(`[copy-vad] missing ${src} - run npm install first`);
    process.exit(1);
  }
  copyFileSync(src, join(out, name));
}
console.log("[copy-vad] assets copied to public/vad");
