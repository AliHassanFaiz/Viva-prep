import { MicVAD } from "@ricky0123/vad-web";
import { useCallback, useEffect, useRef } from "react";
import { settings } from "../lib/settings";

export interface VadHandlers {
  onSpeechStart: () => void;
  onSpeechEnd: (audio: Float32Array) => void;
  onMisfire: () => void;
}

/** Wraps MicVAD. Handlers are read through a ref, so callers never see stale closures. */
export function useVad(handlers: VadHandlers) {
  const h = useRef(handlers);
  h.current = handlers;
  const vad = useRef<MicVAD | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const capTimer = useRef<number>();

  const start = useCallback(async (): Promise<void> => {
    if (vad.current) return;
    const v = await MicVAD.new({
      model: "v5",
      baseAssetPath: "/vad/",
      onnxWASMBasePath: "/vad/",
      startOnLoad: false,
      positiveSpeechThreshold: settings.SPEECH_THRESHOLD,
      negativeSpeechThreshold: Math.max(0.2, settings.SPEECH_THRESHOLD - 0.15),
      redemptionMs: settings.SILENCE_END_MS,
      minSpeechMs: settings.MIN_SPEECH_MS,
      preSpeechPadMs: 300,
      submitUserSpeechOnPause: true, // lets "I'm done" flush the current segment
      getStream: async () => {
        const s = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
        });
        stream.current = s;
        return s;
      },
      // keep the same stream across pause()/start() so flush() never re-prompts for the microphone
      pauseStream: async () => {},
      resumeStream: async (s: MediaStream) => s,
      onSpeechStart: () => {
        window.clearTimeout(capTimer.current);
        capTimer.current = window.setTimeout(() => { void flush(); }, settings.MAX_ANSWER_MS);
        h.current.onSpeechStart();
      },
      onSpeechEnd: (audio: Float32Array) => { window.clearTimeout(capTimer.current); h.current.onSpeechEnd(audio); },
      onVADMisfire: () => { window.clearTimeout(capTimer.current); h.current.onMisfire(); },
    });
    vad.current = v;
    await v.start();
  }, []);

  /** Ends the current segment now ("I'm done" button, or the 2-minute cap). */
  const flush = useCallback(async () => {
    const v = vad.current;
    if (!v) return;
    await v.pause();
    await v.start();
  }, []);

  const stop = useCallback(async () => {
    window.clearTimeout(capTimer.current);
    const v = vad.current;
    vad.current = null;
    try { await v?.destroy(); } catch { /* already destroyed */ }
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  }, []);

  useEffect(() => () => { void stop(); }, [stop]);
  return { start, flush, stop };
}
