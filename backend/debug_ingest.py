"""Runs the REAL upload pipeline on your file, then question generation, then ElevenLabs voice.
Put this file inside the `backend` folder and run:
    python debug_ingest.py "C:\\path\\to\\your_report.pdf"
"""
import asyncio
import os
import sys
import time
import uuid


def line(t):
    print("\n" + "=" * 8, t)


async def main(path: str):
    from app.db import SessionLocal, init_db
    from app.models import Document, User
    from app.services import ingest, question_gen, tts

    name = os.path.basename(path)
    data = open(path, "rb").read()
    print("File:", name, f"({len(data) / 1024:.0f} KB)")

    await init_db()
    uid = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(User(id=uid))
        await db.commit()
        doc = Document(user_id=uid, filename=name, status="processing")
        db.add(doc)
        await db.commit()
        doc_id = doc.id

    line("1. Reading + indexing the file (real ingest)")
    t = time.time()
    try:
        await asyncio.wait_for(ingest.run_ingest(doc_id, name, data), 120)
    except asyncio.TimeoutError:
        print("[STUCK] ingest did not finish in 120s")
        return
    async with SessionLocal() as db:
        d = await db.get(Document, doc_id)
        print(f"status={d.status}  error={d.error}  pages={d.page_count}  chunks={d.chunk_count}  ({time.time() - t:.1f}s)")
        if d.status != "ready":
            print("[FAIL] ingest failed - see message above")
            return
    print("[OK]   ingest")

    line("2. Writing questions (Groq)")
    t = time.time()
    try:
        async with SessionLocal() as db:
            items = await asyncio.wait_for(question_gen.generate(db, doc_id, 3), 90)
        for i in items:
            print(" -", i["text"])
        print(f"[OK]   questions ({time.time() - t:.1f}s)")
    except asyncio.TimeoutError:
        print("[STUCK] questions took longer than 90s")
    except Exception as e:
        print(f"[FAIL] questions - {type(e).__name__}: {str(e)[:400]}")

    line("3. ElevenLabs voice")
    try:
        audio = await asyncio.wait_for(tts.synth_mp3("Hello, this is a test."), 30)
        print(f"[OK]   voice works ({len(audio)} bytes of audio)")
    except Exception as e:
        print(f"[FAIL] voice - {type(e).__name__}: {str(e)[:300]}")

    print("\nDONE. Send everything above to Claude.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python debug_ingest.py "C:\\path\\to\\report.pdf"')
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
