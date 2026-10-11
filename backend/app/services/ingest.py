"""Upload -> parse -> chunk -> embed -> store (SPEC section 7)."""
import asyncio
import io
import re
import uuid

from sqlalchemy import delete

from ..config import settings
from ..db import SessionLocal
from ..logging_utils import log_stage, logger, timed
from ..models import Chunk, Document
from . import qdrant_store
from .chunking import Block, chunk_blocks
from .embeddings import embed_passages
from .vocab import build_vocab_hint

NO_TEXT_MSG = "No text found. Scanned PDFs are not supported."
_HEADING_RE = re.compile(
    r"^(?:(?:chapter|section)\s+\d+[.:]?\s+.{2,80}|\d+(?:\.\d+){0,3}\.?\s+[A-Z][^\n]{2,80}|"
    r"(?:abstract|introduction|background|related work|literature review|methodology|methods|"
    r"system design|implementation|results|evaluation|discussion|limitations|future work|conclusion|conclusions|references)"
    r"|[A-Z][A-Z0-9 \-&,:]{3,70})$", re.I)


class IngestError(Exception):
    pass


def _is_heading(line: str) -> bool:
    line = line.strip()
    if not (3 <= len(line) <= 90) or line.endswith((".", ",", ";")) and not re.match(r"^\d", line):
        return False
    if line.count(" ") > 12:
        return False
    # a "heading" regex match that is all-caps or starts with a number or a known heading word
    if re.match(r"^[A-Z0-9 \-&,:]{4,70}$", line) or re.match(r"^\d+(\.\d+){0,3}\.?\s+[A-Z]", line):
        return not re.fullmatch(r"[\d\W]+", line)
    return bool(re.match(r"^(chapter|section)\s+\d+|^(abstract|introduction|background|related work|literature review|"
                         r"methodology|methods|system design|implementation|results|evaluation|discussion|"
                         r"limitations|future work|conclusions?)\b", line, re.I)) and len(line.split()) <= 6


def _parse_pdf(data: bytes) -> tuple[list[Block], int]:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise IngestError("This PDF is password protected.")
        n_pages = len(reader.pages)
    except IngestError:
        raise
    except Exception:
        raise IngestError("Could not read this PDF. The file may be corrupted.")
    if n_pages > settings.MAX_PDF_PAGES:
        raise IngestError(f"PDF has {n_pages} pages. The limit is {settings.MAX_PDF_PAGES}.")

    blocks: list[Block] = []
    section: str | None = None
    buf: list[str] = []
    buf_page: int | None = None

    def flush():
        nonlocal buf
        text = "\n".join(buf).strip()
        if text:
            blocks.append(Block(section, buf_page, text))
        buf = []

    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        for line in text.splitlines():
            if _is_heading(line):
                flush()
                section = line.strip()[:120]
                buf_page = i
                continue
            if not buf:
                buf_page = i
            buf.append(line)
    flush()
    return blocks, n_pages


def _parse_docx(data: bytes) -> tuple[list[Block], int]:
    from docx import Document as Docx
    try:
        doc = Docx(io.BytesIO(data))
    except Exception:
        raise IngestError("Could not read this Word file. The file may be corrupted.")
    blocks: list[Block] = []
    section: str | None = None
    buf: list[str] = []

    def flush():
        nonlocal buf
        text = "\n".join(buf).strip()
        if text:
            blocks.append(Block(section, None, text))
        buf = []

    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        style = (p.style.name if p.style is not None else "") or ""
        if style.lower().startswith(("heading", "title")):
            flush()
            section = t[:120]
        else:
            buf.append(t)
    flush()
    for table in doc.tables:  # tables often hold results; include them as plain text
        rows = [" | ".join(c.text.strip() for c in r.cells) for r in table.rows]
        txt = "\n".join(r for r in rows if r.strip(" |"))
        if txt:
            blocks.append(Block("Table", None, txt))
    approx_pages = max(1, sum(len(b.text) for b in blocks) // 3000)
    return blocks, approx_pages


def parse_file(filename: str, data: bytes) -> tuple[list[Block], int]:
    low = filename.lower()
    if low.endswith(".pdf"):
        blocks, pages = _parse_pdf(data)
    elif low.endswith(".docx"):
        blocks, pages = _parse_docx(data)
    else:
        raise IngestError("Unsupported file type. Upload a PDF or DOCX.")
    if sum(len(b.text.strip()) for b in blocks) < 60:
        raise IngestError(NO_TEXT_MSG)
    return blocks, pages


async def run_ingest(document_id: uuid.UUID, filename: str, data: bytes) -> None:
    """Background task. The uploaded bytes are never stored; only extracted chunks are."""
    doc_id = str(document_id)
    try:
        with timed() as t:
            blocks, pages = await asyncio.to_thread(parse_file, filename, data)
            chunks = chunk_blocks(blocks)
            if not chunks:
                raise IngestError(NO_TEXT_MSG)
            full_text = "\n".join(b.text for b in blocks)
            vocab = await asyncio.to_thread(build_vocab_hint, full_text)
            ids = [uuid.uuid4() for _ in chunks]
            vectors = await embed_passages([c.text for c in chunks])
            await qdrant_store.upsert_chunks(
                doc_id,
                [{"chunk_id": str(i), "position": c.position, "section": c.section, "page": c.page}
                 for i, c in zip(ids, chunks)],
                vectors)
            async with SessionLocal() as db:
                db.add_all([Chunk(id=i, document_id=document_id, position=c.position, section=c.section,
                                  page=c.page, text=c.text) for i, c in zip(ids, chunks)])
                doc = await db.get(Document, document_id)
                if doc is None:  # deleted while processing
                    await qdrant_store.delete_document(doc_id)
                    await db.rollback()
                    return
                doc.status, doc.page_count, doc.chunk_count, doc.vocab_hint, doc.error = \
                    "ready", pages, len(chunks), vocab, None
                await db.commit()
        log_stage(None, None, "ingest", t["ms"], document_id=doc_id, chunks=len(chunks))
    except IngestError as e:
        await _fail(document_id, str(e))
    except Exception as e:
        logger.error('{"stage":"ingest_failed","error":"%s","detail":"%s"}', type(e).__name__, str(e)[:200].replace('"', "'"))
        await qdrant_store.delete_document(doc_id)
        await _fail(document_id, "Processing failed. Please try again.")


async def _fail(document_id: uuid.UUID, message: str) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        doc = await db.get(Document, document_id)
        if doc:
            doc.status, doc.error = "failed", message
        await db.commit()
