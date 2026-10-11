"""Speech to text (SPEC 10.4)."""
import asyncio
import io
import time
from dataclasses import dataclass

import groq

from ..config import settings
from ..logging_utils import log_stage
from .groq_client import LLMError, client

SILENCE_ARTEFACTS = {"thank you.", "thanks for watching.", "you", "bye."}


@dataclass
class Transcript:
    text: str
    no_speech_probs: list[float]
    ms: float


class STTError(Exception):
    pass


def _seg_value(seg, key: str):
    return seg.get(key) if isinstance(seg, dict) else getattr(seg, key, None)


async def transcribe(wav: bytes, vocab_hint: str | None, session_id=None, turn_id=None) -> Transcript:
    last: Exception | None = None
    for attempt in range(2):  # one retry
        t0 = time.perf_counter()
        try:
            kwargs = dict(file=("answer.wav", wav), model=settings.MODEL_STT, language="en",
                          response_format="verbose_json", temperature=0.0)
            if vocab_hint:
                kwargs["prompt"] = vocab_hint[:800]
            resp = await asyncio.wait_for(client().audio.transcriptions.create(**kwargs), timeout=settings.STT_TIMEOUT_S)
            ms = (time.perf_counter() - t0) * 1000
            text = (getattr(resp, "text", None) or (resp.get("text") if isinstance(resp, dict) else "") or "").strip()
            segs = getattr(resp, "segments", None) or (resp.get("segments") if isinstance(resp, dict) else None) or []
            probs = [float(p) for p in (_seg_value(s, "no_speech_prob") for s in segs) if p is not None]
            log_stage(session_id, turn_id, "stt", ms, attempt=attempt + 1)
            return Transcript(text, probs, ms)
        except groq.RateLimitError as e:
            last = e
            try:
                wait = float(e.response.headers.get("retry-after", 1.5))
            except Exception:
                wait = 1.5
            await asyncio.sleep(min(wait, 5))
        except (asyncio.TimeoutError, groq.APIConnectionError, groq.InternalServerError) as e:
            last = e
            await asyncio.sleep(0.3)
        except (groq.APIStatusError, LLMError) as e:
            last = e
            break
    raise STTError(f"STT failed: {type(last).__name__}")


def is_silence(text: str, no_speech_probs: list[float], duration_ms: int | None) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if duration_ms is not None:
        if duration_ms < 600:
            return True
        if t.lower() in SILENCE_ARTEFACTS and duration_ms < 2500:
            return True
    if no_speech_probs and all(p > settings.NO_SPEECH_PROB_MAX for p in no_speech_probs):
        return True
    return False
