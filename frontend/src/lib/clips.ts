// Mirrors backend/app/static_clips.py. Used as the spoken text when an mp3 clip is missing (browser voice fallback).
export const CLIP_TEXT: Record<string, string> = {
  greeting: "Hello, I'll be asking you a few questions based on your document. Take your time and answer as you would in the real thing.",
  filler_1: "Okay.", filler_2: "Mm-hm.", filler_3: "I see.", filler_4: "Right.",
  repeat_prompt: "Sorry, I didn't catch that. Could you say that again?",
  nudge: "Would you like me to repeat the question?",
  closing: "Thank you. That's all my questions. Your feedback will be ready in a moment.",
};
export const STATIC_NAMES = Object.keys(CLIP_TEXT);
