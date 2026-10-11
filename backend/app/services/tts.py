"""ElevenLabs text to speech (SPEC 10.6): full mp3 for questions/static clips, streamed PCM for follow-ups."""
import httpx

from ..config import settings

BASE = "https://api.elevenlabs.io/v1/text-to-speech"


class TTSError(Exception):
    pass


def _check() -> None:
    if not settings.ELEVENLABS_API_KEY or not settings.ELEVENLABS_VOICE_ID:
        raise TTSError("ElevenLabs is not configured.")


def _headers() -> dict:
    return {"xi-api-key": settings.ELEVENLABS_API_KEY, "Content-Type": "application/json"}


def _body(text: str) -> dict:
    return {"text": text, "model_id": settings.ELEVENLABS_MODEL}


async def synth_mp3(text: str) -> bytes:
    _check()
    url = f"{BASE}/{settings.ELEVENLABS_VOICE_ID}?output_format=mp3_44100_128"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.TTS_TIMEOUT_S, connect=5)) as c:
            r = await c.post(url, headers=_headers(), json=_body(text))
    except httpx.HTTPError as e:
        raise TTSError(f"TTS request failed: {type(e).__name__}")
    if r.status_code != 200 or not r.content:
        raise TTSError(f"TTS HTTP {r.status_code}")
    return r.content


# (output_format, sample_rate). Tried in order; the last resort is a full mp3 delivered as one chunk.
_PCM_FORMATS = [("pcm_24000", 24000), ("pcm_22050", 22050), ("pcm_16000", 16000)]


async def stream_audio(text: str):
    """Async generator. First yields ("meta", format, sample_rate) with format 'pcm_s16le' or 'mp3',
    then yields raw bytes (even-length for PCM). Cancelling the consuming task closes the HTTP stream."""
    _check()
    timeout = httpx.Timeout(settings.TTS_TIMEOUT_S, connect=5, read=settings.TTS_TIMEOUT_S)
    async with httpx.AsyncClient(timeout=timeout) as c:
        for fmt, rate in _PCM_FORMATS:
            url = f"{BASE}/{settings.ELEVENLABS_VOICE_ID}/stream?output_format={fmt}"
            try:
                async with c.stream("POST", url, headers=_headers(), json=_body(text)) as r:
                    if r.status_code != 200:
                        continue  # format not allowed on this plan: try the next one
                    yield ("meta", "pcm_s16le", rate)
                    carry = b""
                    async for piece in r.aiter_bytes(chunk_size=4096):
                        data = carry + piece
                        if len(data) % 2:
                            data, carry = data[:-1], data[-1:]
                        else:
                            carry = b""
                        if data:
                            yield data
                    return
            except httpx.HTTPError as e:
                raise TTSError(f"TTS stream failed: {type(e).__name__}")
    # last resort: whole mp3 as a single chunk
    mp3 = await synth_mp3(text)
    yield ("meta", "mp3", 44100)
    yield mp3
