import { useEffect, useRef } from "react";
import { b64ToBytes } from "../lib/audio";

interface Item {
  turnId?: string;
  run: () => Promise<void>;
  cancel: () => void;
}

class PcmStream {
  private nextStart = 0;
  private sources = new Set<AudioBufferSourceNode>();
  private pending: Float32Array[] = [];
  private pendingSecs = 0;
  private started = false;
  private ended = false;
  private aborted = false;
  private mp3: Uint8Array[] = [];
  private resolve: (() => void) | null = null;

  constructor(private ctx: AudioContext, private rate: number, private format: string) {}

  push(b64: string) {
    if (this.aborted) return;
    const bytes = b64ToBytes(b64);
    if (this.format === "mp3") { this.mp3.push(bytes); return; }
    const n = Math.floor(bytes.length / 2);
    const f32 = new Float32Array(n);
    const dv = new DataView(bytes.buffer, bytes.byteOffset, n * 2);
    for (let i = 0; i < n; i++) f32[i] = dv.getInt16(i * 2, true) / 32768;
    if (!this.started) {
      this.pending.push(f32);
      this.pendingSecs += n / this.rate;
      if (this.pendingSecs >= 0.12) this.flushPending(); // wait for a little audio first to avoid stutter
    } else this.schedule(f32);
  }

  private flushPending() {
    this.started = true;
    this.pending.forEach((p) => this.schedule(p));
    this.pending = [];
  }

  private schedule(f32: Float32Array) {
    const buf = this.ctx.createBuffer(1, f32.length, this.rate);
    buf.copyToChannel(f32 as Float32Array<ArrayBuffer>, 0);
    this.play(buf);
  }

  private play(buf: AudioBuffer) {
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.ctx.destination);
    const at = Math.max(this.nextStart, this.ctx.currentTime + 0.05);
    src.start(at);
    this.nextStart = at + buf.duration;
    this.sources.add(src);
    src.onended = () => { this.sources.delete(src); this.check(); };
  }

  async end() {
    this.ended = true;
    if (this.aborted) return;
    if (this.format === "mp3") {
      try {
        const total = this.mp3.reduce((a, b) => a + b.length, 0);
        const all = new Uint8Array(total);
        let o = 0;
        for (const b of this.mp3) { all.set(b, o); o += b.length; }
        this.play(await this.ctx.decodeAudioData(all.buffer.slice(0) as ArrayBuffer));
      } catch { /* undecodable: finish silently */ }
    } else if (!this.started) this.flushPending();
    this.check();
  }

  private check() {
    if (this.ended && this.sources.size === 0 && this.resolve) { const r = this.resolve; this.resolve = null; r(); }
  }

  abort() {
    this.aborted = true;
    this.sources.forEach((s) => { try { s.onended = null; s.stop(); } catch { /* already stopped */ } });
    this.sources.clear();
    if (this.resolve) { const r = this.resolve; this.resolve = null; r(); }
  }

  wait(): Promise<void> {
    return new Promise((res) => { this.resolve = res; this.check(); });
  }
}

/** Single FIFO player: cached blobs, browser-voice speech, and streamed PCM. Fires onFinished(turnId) when the queue drains. */
export class Player {
  private queue: Item[] = [];
  private current: Item | null = null;
  private gen = 0;
  private running = false;
  private ctx: AudioContext | null = null;
  private streams = new Map<string, PcmStream>();
  speaking = false;
  onFinished: (turnId: string) => void = () => {};
  onSpeakingChange: (s: boolean) => void = () => {};

  /** Call from a click handler so the browser allows audio. */
  unlock() {
    if (!this.ctx) this.ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    if (this.ctx.state === "suspended") void this.ctx.resume();
  }

  enqueueBlob(blob: Blob, turnId?: string) {
    let el: HTMLAudioElement | null = null;
    let url = "";
    let done: (() => void) | null = null;
    this.push({
      turnId,
      run: () => new Promise<void>((resolve) => {
        done = resolve;
        url = URL.createObjectURL(blob);
        el = new Audio(url);
        el.onended = () => resolve();
        el.onerror = () => resolve();
        el.play().catch(() => resolve());
      }).finally(() => { if (url) URL.revokeObjectURL(url); }),
      cancel: () => { try { el?.pause(); } catch { /* noop */ } done?.(); },
    });
  }

  enqueueSpeech(text: string, turnId?: string) {
    let done: (() => void) | null = null;
    this.push({
      turnId,
      run: () => new Promise<void>((resolve) => {
        done = resolve;
        if (!("speechSynthesis" in window) || !text) { resolve(); return; }
        const u = new SpeechSynthesisUtterance(text);
        u.lang = "en-US";
        u.onend = () => resolve();
        u.onerror = () => resolve();
        window.speechSynthesis.speak(u);
      }),
      cancel: () => { try { window.speechSynthesis?.cancel(); } catch { /* noop */ } done?.(); },
    });
  }

  startStream(turnId: string, rate: number, format: string) {
    this.unlock();
    this.streams.get(turnId)?.abort();
    const s = new PcmStream(this.ctx!, rate, format);
    this.streams.set(turnId, s);
    this.push({ turnId, run: () => s.wait(), cancel: () => s.abort() });
  }
  pushChunk(turnId: string, b64: string) { this.streams.get(turnId)?.push(b64); }
  endStream(turnId: string) { void this.streams.get(turnId)?.end(); }
  abortStream(turnId: string) { this.streams.get(turnId)?.abort(); this.streams.delete(turnId); }

  stopAll() {
    this.gen++;
    this.queue = [];
    this.streams.forEach((s) => s.abort());
    this.streams.clear();
    this.current?.cancel();
    this.current = null;
    try { window.speechSynthesis?.cancel(); } catch { /* noop */ }
    this.setSpeaking(false);
  }

  private setSpeaking(s: boolean) {
    if (this.speaking !== s) { this.speaking = s; this.onSpeakingChange(s); }
  }

  private push(item: Item) {
    this.queue.push(item);
    void this.pump();
  }

  private async pump() {
    if (this.running) return;
    this.running = true;
    const gen = this.gen;
    let lastTurn: string | undefined;
    while (this.queue.length && gen === this.gen) {
      const item = this.queue.shift()!;
      this.current = item;
      this.setSpeaking(true);
      await item.run();
      if (gen !== this.gen) { this.running = false; if (this.queue.length) void this.pump(); return; }
      if (item.turnId) lastTurn = item.turnId;
    }
    this.running = false;
    this.current = null;
    if (gen !== this.gen) { if (this.queue.length) void this.pump(); return; }
    this.setSpeaking(false);
    if (lastTurn) { this.streams.delete(lastTurn); this.onFinished(lastTurn); }
  }
}

export function useAudioQueue() {
  const ref = useRef<Player>();
  if (!ref.current) ref.current = new Player();
  useEffect(() => () => ref.current?.stopAll(), []);
  return ref.current;
}
