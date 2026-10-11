"""Generate the static clips once and write them to frontend/public/audio/ (SPEC section 13).
Usage (from backend/):  python -m scripts.make_static_audio"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.services import tts  # noqa: E402
from app.static_clips import STATIC_CLIPS  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "public" / "audio"


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in STATIC_CLIPS.items():
        data = await tts.synth_mp3(text)
        (OUT / f"{name}.mp3").write_bytes(data)
        print(f"wrote {name}.mp3 ({len(data) // 1024} KB)")


if __name__ == "__main__":
    asyncio.run(main())
