from app.services.chunking import Block, chunk_blocks
from app.services.evaluator import band_for, question_score
from app.services.stt import is_silence
from app.services.token_budget import TokenBudget
from app.services.vocab import build_vocab_hint
from app.services.ingest import _is_heading


def test_chunking_sizes_and_overlap():
    text = ("Sentence number one is here. " * 200).strip()
    ch = chunk_blocks([Block("Intro", 1, text)])
    assert len(ch) > 3
    assert all(200 <= len(c.text) <= 1500 for c in ch)
    assert [c.position for c in ch] == list(range(len(ch)))


def test_tiny_document_is_kept():
    ch = chunk_blocks([Block(None, 1, "A short but real paragraph about a viva project that is under the limit.")])
    assert len(ch) == 1


def test_vocab_hint_limits():
    text = ("The RAG pipeline uses Qdrant and FastAPI. " * 20) + ("transformer embeddings retrieval " * 10)
    hint = build_vocab_hint(text)
    assert hint.startswith("Technical terms:") and len(hint) <= 600 and "RAG" in hint


def test_scoring_formulas():
    assert question_score(dict(accuracy=4, completeness=3, clarity=4, justification=2)) == 65
    assert band_for(49) == "needs_work" and band_for(50) == "developing" and band_for(74) == "developing" and band_for(75) == "ready"


def test_silence_rules():
    assert is_silence("", [], 3000)
    assert is_silence("hello there", [], 500)
    assert is_silence("Thank you.", [0.1], 1500)
    assert not is_silence("Thank you.", [0.1], 4000)
    assert is_silence("some text", [0.9, 0.8], 3000)
    assert not is_silence("some text", [0.9, 0.1], 3000)
    assert not is_silence("typed answer", [], None)


def test_heading_detection():
    assert _is_heading("3.2 Methodology")
    assert _is_heading("RESULTS AND DISCUSSION")
    assert not _is_heading("This is just a normal sentence that ends with a period.")


async def test_token_budget_blocks_then_allows():
    b = TokenBudget(1000)
    b.record("m", 900)
    import asyncio
    t = asyncio.create_task(b.acquire("m", 200))
    await asyncio.sleep(0.4)
    assert not t.done()
    t.cancel()
    await b.acquire("m", 50)
