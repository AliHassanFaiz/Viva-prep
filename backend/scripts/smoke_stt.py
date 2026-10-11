"""Day-one smoke tests (SPEC section 16).
  python -m scripts.smoke_stt answer.wav        # WAV -> Whisper
  python -m scripts.smoke_stt --tts             # ElevenLabs mp3 + streamed PCM
  python -m scripts.smoke_stt --qdrant          # insert + filtered search"""
import asyncio
import pathlib
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.services import qdrant_store, stt, tts  # noqa: E402


async def main(arg: str) -> None:
    if arg == "--tts":
        t = time.perf_counter()
        mp3 = await tts.synth_mp3("Why did you choose Qdrant for retrieval?")
        print(f"mp3 ok: {len(mp3)} bytes in {(time.perf_counter() - t) * 1000:.0f} ms")
        t, n, fmt = time.perf_counter(), 0, None
        first = None
        async for item in tts.stream_audio("Could you explain that reason in more detail?"):
            if isinstance(item, tuple):
                fmt = item[1:]
                continue
            first = first or (time.perf_counter() - t) * 1000
            n += len(item)
        print(f"stream ok: format={fmt} {n} bytes, first chunk {first:.0f} ms")
    elif arg == "--qdrant":
        doc = str(uuid.uuid4())
        vec = [0.1] * 384
        await qdrant_store.upsert_chunks(doc, [{"chunk_id": str(uuid.uuid4()), "position": 0}], [vec])
        print("search with filter:", await qdrant_store.search(doc, vec, 1))
        print("search other doc  :", await qdrant_store.search(str(uuid.uuid4()), vec, 1))
        await qdrant_store.delete_document(doc)
    else:
        wav = pathlib.Path(arg).read_bytes()
        tr = await stt.transcribe(wav, "Technical terms: Qdrant, FastAPI, LangGraph.")
        print(f"{tr.ms:.0f} ms | no_speech_probs={tr.no_speech_probs}\n{tr.text}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "--qdrant"))
