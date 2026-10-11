"""Split sectioned text into ~1500 char chunks with 200 char overlap (SPEC section 7, ingest step 3)."""
from dataclasses import dataclass

from ..config import settings


@dataclass
class Block:
    section: str | None
    page: int | None
    text: str


@dataclass
class ChunkOut:
    position: int
    section: str | None
    page: int | None
    text: str


def _split(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # prefer to cut at a paragraph, sentence or word boundary in the last 25% of the window
            window_start = start + int(size * 0.75)
            cut = -1
            for sep in ("\n\n", "\n", ". ", "? ", "! ", " "):
                cut = text.rfind(sep, window_start, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return out


def chunk_blocks(blocks: list[Block]) -> list[ChunkOut]:
    chunks: list[ChunkOut] = []
    for b in blocks:
        for piece in _split(b.text, settings.CHUNK_CHARS, settings.CHUNK_OVERLAP):
            chunks.append(ChunkOut(len(chunks), b.section, b.page, piece))
    kept = [c for c in chunks if len(c.text) >= settings.CHUNK_MIN_CHARS]
    if not kept and chunks:
        # tiny document: keep what we have rather than failing
        joined = "\n\n".join(c.text for c in chunks)
        if len(joined) >= 60:
            kept = [ChunkOut(0, chunks[0].section, chunks[0].page, joined[: settings.CHUNK_CHARS])]
    for i, c in enumerate(kept):
        c.position = i
    return kept
