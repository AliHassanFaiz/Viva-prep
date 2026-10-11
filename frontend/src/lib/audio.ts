import { api } from "./api";
import { CLIP_TEXT, STATIC_NAMES } from "./clips";
import type { SessionCreated, SessionDetail } from "./types";

/** audio id -> Blob. Ids: greeting, q:<session_question_id>, filler_1..4, repeat_prompt, nudge, closing. */
export const audioCache = new Map<string, Blob>();
const loadedSessions = new Set<string>();

export function isSessionLoaded(sessionId: string) { return loadedSessions.has(sessionId); }

async function fetchStatic(name: string): Promise<Blob | null> {
  try {
    const res = await fetch(`/audio/${name}.mp3`);
    const type = res.headers.get("content-type") || "";
    // the dev server answers missing files with index.html (200), so check the type
    if (!res.ok || !type.startsWith("audio")) return null;
    const b = await res.blob();
    return b.size > 0 ? b : null;
  } catch { return null; }
}

/** Download question audio and static clips. Missing items are simply absent: the player then uses the browser voice. */
export async function preloadSession(
  data: Pick<SessionCreated | SessionDetail, "questions" | "static_audio"> & { session_id?: string; id?: string },
  onProgress?: (done: number, total: number) => void,
): Promise<{ missingQuestions: number }> {
  const sid = data.session_id ?? data.id ?? "";
  const jobs: Array<() => Promise<void>> = [];
  let missingQuestions = 0;
  for (const q of data.questions) {
    jobs.push(async () => {
      const key = `q:${q.session_question_id}`;
      if (audioCache.has(key)) return;
      const blob = q.audio_url ? await api.fetchAudio(q.audio_url) : null;
      if (blob) audioCache.set(key, blob); else missingQuestions++;
    });
  }
  for (const name of data.static_audio?.length ? data.static_audio : STATIC_NAMES) {
    jobs.push(async () => {
      if (audioCache.has(name)) return;
      const blob = await fetchStatic(name);
      if (blob) audioCache.set(name, blob);
    });
  }
  let done = 0;
  await Promise.all(jobs.map((j) => j().finally(() => onProgress?.(++done, jobs.length))));
  if (sid) loadedSessions.add(sid);
  return { missingQuestions };
}

export function textForAudioId(id: string, questions: { session_question_id: string; text: string }[]): string {
  if (id.startsWith("q:")) return questions.find((q) => q.session_question_id === id.slice(2))?.text ?? "";
  return CLIP_TEXT[id] ?? "";
}

// ---------- recording helpers ----------
/** Float32 mono @16 kHz -> 16-bit PCM WAV. */
export function encodeWav(samples: Float32Array, sampleRate = 16000): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const w = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  w(36, "data"); v.setUint32(40, samples.length * 2, true);
  let o = 44;
  for (let i = 0; i < samples.length; i++, o += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buf], { type: "audio/wav" });
}

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

export function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
