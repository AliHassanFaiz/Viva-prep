import { useCallback, useEffect, useRef, useState } from "react";
import { audioCache, blobToBase64, encodeWav, textForAudioId } from "../lib/audio";
import { settings, WS_URL } from "../lib/settings";
import type { CallState, SessionQuestion } from "../lib/types";
import { api } from "../lib/api";
import { newId } from "../lib/userId";
import { CallSocket, type WsStatus } from "../lib/ws";
import { useAudioQueue } from "./useAudioQueue";
import { useVad } from "./useVad";

export interface Caption { id: string; who: "examiner" | "student"; text: string; kind?: string }
export type Phase = "lobby" | "connecting" | "live" | "ended";

interface Options {
  sessionId: string;
  questions: SessionQuestion[];
  allowInterruptions: boolean;
  onEnded: () => void;
}

export function useCall({ sessionId, questions, allowInterruptions, onEnded }: Options) {
  const player = useAudioQueue();
  const [phase, setPhase] = useState<Phase>("lobby");
  const [state, setStateRaw] = useState<CallState>("idle");
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [qIndex, setQIndex] = useState(0);
  const [wsStatus, setWsStatus] = useState<WsStatus>("connecting");
  const [micOk, setMicOk] = useState(true);
  const [micError, setMicError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [textFallback, setTextFallback] = useState(false);
  const [userSpeaking, setUserSpeaking] = useState(false);

  const stateRef = useRef<CallState>("idle");
  const socket = useRef<CallSocket | null>(null);
  const turnRef = useRef<string | null>(null);
  const speechStartedAt = useRef(0);
  const inSpeech = useRef(false);
  const bargeTimer = useRef<number>();
  const allowRef = useRef(allowInterruptions);
  allowRef.current = allowInterruptions;
  const qRef = useRef(questions);
  qRef.current = questions;
  const endedRef = useRef(false);
  const onEndedRef = useRef(onEnded);
  onEndedRef.current = onEnded;

  const setState = useCallback((s: CallState) => { stateRef.current = s; setStateRaw(s); }, []);
  const addCaption = useCallback((c: Omit<Caption, "id">) => setCaptions((p) => [...p, { ...c, id: newId() }]), []);
  const flashNotice = useCallback((msg: string) => { setNotice(msg); window.setTimeout(() => setNotice((n) => (n === msg ? null : n)), 5000); }, []);

  // ---------- microphone / VAD ----------
  const doBargeIn = useCallback(() => {
    player.stopAll();
    if (turnRef.current) socket.current?.send({ type: "barge_in", turn_id: turnRef.current });
    setState("listening");
  }, [player, setState]);

  const vad = useVad({
    onSpeechStart: () => {
      inSpeech.current = true;
      speechStartedAt.current = performance.now();
      setUserSpeaking(true);
      socket.current?.send({ type: "speech_start" });
      if (stateRef.current === "speaking" && allowRef.current) {
        window.clearTimeout(bargeTimer.current);
        bargeTimer.current = window.setTimeout(() => {
          if (inSpeech.current && stateRef.current === "speaking") doBargeIn();
        }, settings.BARGE_IN_MIN_MS);
      }
    },
    onMisfire: () => { inSpeech.current = false; setUserSpeaking(false); window.clearTimeout(bargeTimer.current); },
    onSpeechEnd: (audio) => {
      const decidedAt = performance.now();
      inSpeech.current = false;
      setUserSpeaking(false);
      window.clearTimeout(bargeTimer.current);
      if (stateRef.current !== "listening") return; // examiner still talking (interruptions off) or already thinking
      const durationMs = Math.round((audio.length / 16000) * 1000);
      const turnId = newId();
      setState("thinking");
      void blobToBase64(encodeWav(audio)).then((data) => {
        const ok = socket.current?.send({
          type: "answer_audio", turn_id: turnId, mime: "audio/wav", data, duration_ms: durationMs,
          client_silence_to_send_ms: Math.round(performance.now() - decidedAt),
        });
        if (!ok) { setState("listening"); flashNotice("Connection lost. Your answer wasn't sent - please say it again."); return; }
        const fillers = ["filler_1", "filler_2", "filler_3", "filler_4"].filter((f) => audioCache.has(f));
        if (fillers.length) player.enqueueBlob(audioCache.get(fillers[Math.floor(Math.random() * fillers.length)])!);
      });
    },
  });

  // ---------- server messages ----------
  const onMessage = useCallback((m: any) => {
    switch (m.type) {
      case "ready":
        setQIndex(m.current_index ?? 0);
        break;
      case "state":
        if (m.state === "ended") { setState("ended"); if (!endedRef.current) { endedRef.current = true; setPhase("ended"); void vad.stop(); onEndedRef.current(); } }
        else if (!(m.state === "listening" && player.speaking)) setState(m.state);
        break;
      case "play_cached": {
        turnRef.current = m.turn_id;
        const ids: string[] = m.audio_ids;
        ids.forEach((id) => {
          const blob = audioCache.get(id);
          if (blob) player.enqueueBlob(blob, m.turn_id);
          else player.enqueueSpeech(textForAudioId(id, qRef.current), m.turn_id);
          if (id.startsWith("q:")) {
            const idx = qRef.current.findIndex((q) => q.session_question_id === id.slice(2));
            if (idx >= 0) setQIndex(idx);
          }
        });
        addCaption({ who: "examiner", text: m.text, kind: ids.includes("closing") ? "closing" : "question" });
        break;
      }
      case "examiner_text":
        turnRef.current = m.turn_id;
        addCaption({ who: "examiner", text: m.text, kind: m.kind });
        break;
      case "tts_start": turnRef.current = m.turn_id; player.startStream(m.turn_id, m.sample_rate, m.format); break;
      case "tts_chunk": player.pushChunk(m.turn_id, m.data); break;
      case "tts_end": player.endStream(m.turn_id); break;
      case "transcript": addCaption({ who: "student", text: m.text }); break;
      case "error":
        if (m.fallback === "text_input") { setTextFallback(true); flashNotice(m.message); if (stateRef.current === "thinking") setState("listening"); }
        else if (m.fallback === "browser_voice") {
          if (m.turn_id) { player.abortStream(m.turn_id); player.enqueueSpeech(m.text ?? "", m.turn_id); }
          flashNotice("Using your browser's voice for this reply.");
        } else flashNotice(m.message);
        break;
    }
  }, [addCaption, flashNotice, player, setState, vad]);

  // ---------- lifecycle ----------
  const start = useCallback(async () => {
    setPhase("connecting");
    player.unlock(); // inside the click handler, so audio is allowed
    player.onFinished = (turnId) => socket.current?.send({ type: "playback_finished", turn_id: turnId });
    try {
      await vad.start();
      setMicOk(true);
    } catch (e: any) {
      setMicOk(false);
      setTextFallback(true);
      setMicError(e?.name === "NotAllowedError" ? "Microphone access was blocked. You can still type your answers."
        : "No microphone could be started. You can still type your answers.");
    }
    const s = new CallSocket(async () => {
      const { token } = await api.wsToken(sessionId);
      return `${WS_URL}/ws/call/${sessionId}?token=${encodeURIComponent(token)}`;
    }, {
      onMessage,
      onStatus: setWsStatus,
      onOpen: () => { setPhase("live"); s.send({ type: "start" }); },
    });
    socket.current = s;
    s.connect();
  }, [onMessage, player, sessionId, vad]);

  useEffect(() => () => { socket.current?.close(); window.clearTimeout(bargeTimer.current); }, []);

  const finishSegment = useCallback(async () => {
    if (!inSpeech.current) { flashNotice("Say something first, then press this when you're finished."); return; }
    await vad.flush();
  }, [flashNotice, vad]);

  const sendText = useCallback((text: string) => {
    const t = text.trim();
    if (!t) return;
    if (stateRef.current === "speaking") { player.stopAll(); if (turnRef.current) socket.current?.send({ type: "barge_in", turn_id: turnRef.current }); }
    setState("thinking");
    if (!socket.current?.send({ type: "answer_text", turn_id: newId(), text: t })) { setState("listening"); flashNotice("Connection lost. Try again in a moment."); }
  }, [flashNotice, player, setState]);

  const stopExaminer = useCallback(() => { if (stateRef.current === "speaking") doBargeIn(); }, [doBargeIn]);

  const endCall = useCallback(() => {
    player.stopAll();
    socket.current?.send({ type: "end_call" });
    window.setTimeout(() => { if (!endedRef.current) { endedRef.current = true; void vad.stop(); onEndedRef.current(); } }, 1800);
  }, [player, vad]);

  return {
    phase, state, captions, qIndex, wsStatus, micOk, micError, notice, textFallback, userSpeaking,
    setTextFallback, start, finishSegment, sendText, stopExaminer, endCall,
  };
}
