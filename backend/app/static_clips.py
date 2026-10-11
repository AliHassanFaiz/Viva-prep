"""Texts of the static audio clips (SPEC section 13). Shared by the generator script and the orchestrator."""

STATIC_CLIPS: dict[str, str] = {
    "greeting": "Hello, I'm your examiner today. I'll ask you a few questions about your report. "
    "Take your time and answer as you would in a real viva.",
    "filler_1": "Okay.",
    "filler_2": "Mm-hm.",
    "filler_3": "I see.",
    "filler_4": "Right.",
    "repeat_prompt": "Sorry, I didn't catch that. Could you say that again?",
    "nudge": "Would you like me to repeat the question?",
    "closing": "Thank you. That's all my questions. Your report will be ready in a moment.",
}
STATIC_AUDIO_NAMES = list(STATIC_CLIPS.keys())
