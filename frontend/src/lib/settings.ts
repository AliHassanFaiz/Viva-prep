// Tunable thresholds (SPEC section 3). Change here, no other code needs to move.
export const settings = {
  SILENCE_END_MS: 2500,  // was 1300: a normal thinking pause ended the answer early and the rest was lost
  MIN_SPEECH_MS: 400,
  BARGE_IN_MIN_MS: 300,
  MAX_ANSWER_MS: 120000,
  SPEECH_THRESHOLD: 0.6,
  PING_MS: 20000,
  QUESTIONS_MIN: 2,
  QUESTIONS_MAX: 4,
};

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = (import.meta.env.VITE_WS_URL || API_URL.replace(/^http/, "ws")).replace(/\/$/, "");

const KEY = "viva.allowInterruptions";
export const getAllowInterruptions = () => {
  try { return localStorage.getItem(KEY) !== "0"; } catch { return true; }
};
export const setAllowInterruptions = (v: boolean) => {
  try { localStorage.setItem(KEY, v ? "1" : "0"); } catch { /* storage unavailable */ }
};
