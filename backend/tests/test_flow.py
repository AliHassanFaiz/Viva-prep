import io
import time
import uuid

import pytest

UID = ""
H: dict = {}      # Bearer header of test user A, filled by the autouse fixture below
OTHER: dict = {}  # Bearer header of test user B


def signup(client, email, password="correct-horse-1"):
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


def ws_path(client, sid, headers=None):
    tok = client.post(f"/api/sessions/{sid}/ws-token", headers=headers or H).json()["token"]
    return f"/ws/call/{sid}?token={tok}"


@pytest.fixture(autouse=True)
def _users(client):
    global UID
    if not H:
        h, UID = signup(client, "user-a@example.com")
        H.update(h)
        OTHER.update(signup(client, "user-b@example.com")[0])

REPORT = (
    "Abstract\nThis project builds a retrieval augmented generation system for university students. " * 12
    + "\nMethodology\nWe chose Qdrant because it supports payload filtering and cosine search on 384 dimension vectors. " * 12
    + "\nResults\nThe system reached 87 percent answer accuracy on a test set of 120 questions. " * 12
)


def make_docx() -> bytes:
    from docx import Document
    d = Document()
    for block in REPORT.split("\n"):
        if block in ("Abstract", "Methodology", "Results"):
            d.add_heading(block, level=1)
        elif block:
            d.add_paragraph(block)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def make_pdf(text: str) -> bytes:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for i in range(0, len(text), 90):
        pdf.cell(0, 6, text[i:i + 90], new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    from app.services import decision, evaluator, question_gen, stt, tts
    from app.services.stt import Transcript

    async def fake_chat_json(**kw):
        name = kw["schema_name"]
        if name == "viva_questions":
            ids = [l.split('"')[1] for l in kw["user"].splitlines() if l.startswith("<passage id=")]
            return {"questions": [
                {"question": f"Why did you choose option number {i} for the design?", "topic": f"t{i}",
                 "difficulty": ["basic", "medium", "hard"][i % 3], "key_points": ["reason a", "reason b"],
                 "source_chunk_ids": [ids[0], "not-a-real-id"]} for i in range(3)]}
        if name == "viva_decision":
            ans = kw["user"].split("<student_answer>")[1].split("</student_answer>")[0].lower()
            if "repeat" in ans:
                return {"verdict": "repeat_request", "followup": None, "reason": "asked"}
            if "works well" in ans or "vague" in ans:
                return {"verdict": "vague", "followup": "What was the specific reason?", "reason": "general"}
            return {"verdict": "clear", "followup": "ignored", "reason": "specific"}
        if name == "viva_eval":
            return {"scores": {"accuracy": 4, "completeness": 3, "clarity": 4, "justification": 2}, "covered_points": ["reason a"],
                    "missed_points": ["reason b"], "incorrect_claims": [], "feedback": "You explained well.", "model_answer": "A model answer."}
        return {"strengths": ["s"], "gaps": ["g"], "practice_next": ["p"], "overall_comment": "ok"}

    async def fake_synth(text):
        return b"ID3fakemp3"

    async def fake_stream(text):
        yield ("meta", "pcm_s16le", 24000)
        yield b"\x00\x01" * 100
        yield b"\x00\x02" * 100

    async def fake_transcribe(wav, hint, *a, **k):
        return Transcript("we used qdrant because of payload filtering", [0.01], 120.0)

    for mod in (question_gen, decision, evaluator):
        monkeypatch.setattr(mod, "chat_json", fake_chat_json)
    monkeypatch.setattr(tts, "synth_mp3", fake_synth)
    monkeypatch.setattr(tts, "stream_audio", fake_stream)
    monkeypatch.setattr(stt, "transcribe", fake_transcribe)


def wait_ready(client, doc_id, headers=H):
    for _ in range(50):
        d = client.get(f"/api/documents/{doc_id}", headers=headers).json()
        if d["status"] != "processing":
            return d
        time.sleep(0.1)
    raise AssertionError("ingest timeout")


def test_health_and_auth(client):
    assert client.get("/api/health").json() == {"ok": True}
    r = client.get("/api/sessions")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_upload_validation(client):
    r = client.post("/api/documents", headers=H, files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_type"
    r = client.post("/api/documents", headers=H, files={"file": ("a.pdf", b"", "application/pdf")})
    assert r.status_code == 400


def test_scanned_pdf_fails_with_message(client):
    from fpdf import FPDF
    pdf = FPDF(); pdf.add_page()
    r = client.post("/api/documents", headers=H, files={"file": ("scan.pdf", bytes(pdf.output()), "application/pdf")})
    assert r.status_code == 202
    d = wait_ready(client, r.json()["document_id"])
    assert d["status"] == "failed" and d["error"] == "No text found. Scanned PDFs are not supported."


def test_pdf_ingest(client):
    r = client.post("/api/documents", headers=H, files={"file": ("r.pdf", make_pdf(REPORT.replace("\n", " ")), "application/pdf")})
    d = wait_ready(client, r.json()["document_id"])
    assert d["status"] == "ready" and d["chunk_count"] >= 1


def test_full_flow(client):
    r = client.post("/api/documents", headers=H, files={"file": ("report.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert r.status_code == 202
    doc_id = r.json()["document_id"]
    d = wait_ready(client, doc_id)
    assert d["status"] == "ready", d
    assert client.get(f"/api/documents/{doc_id}", headers=OTHER).status_code == 404  # privacy

    qs = client.post(f"/api/documents/{doc_id}/questions", headers=H, json={"n": 3})
    assert qs.status_code == 200, qs.text
    questions = qs.json()["questions"]
    assert len(questions) == 3 and questions[0]["key_points"]

    # edit + remove
    p = client.patch(f"/api/questions/{questions[0]['id']}", headers=H, json={"text": "Edited question text here?"})
    assert p.json()["text"] == "Edited question text here?"
    assert client.patch(f"/api/questions/{questions[0]['id']}", headers=OTHER, json={"accepted": False}).status_code == 404

    # too few -> 400 ; valid -> 201
    bad = client.post("/api/sessions", headers=H, json={"document_id": doc_id, "question_ids": [questions[0]["id"]]})
    assert bad.status_code == 422
    sc = client.post("/api/sessions", headers=H, json={"document_id": doc_id, "question_ids": [q["id"] for q in questions]})
    assert sc.status_code == 201, sc.text
    body = sc.json()
    sid = body["session_id"]
    assert body["audio_ready"] is True and len(body["questions"]) == 3 and len(body["static_audio"]) == 8
    audio = client.get(body["questions"][0]["audio_url"], headers=H)
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/mpeg"

    uid = UID
    with client.websocket_connect(ws_path(client, sid)) as ws:
        def recv_until(t):
            seen = []
            for _ in range(40):
                m = ws.receive_json()
                seen.append(m)
                if m["type"] == t:
                    return m, seen
            raise AssertionError(f"never got {t}: {seen}")

        ws.send_json({"type": "start"})
        ready, _ = recv_until("ready")
        assert ready["question_count"] == 3
        play, seen = recv_until("play_cached")
        assert play["audio_ids"][0] == "greeting" and play["audio_ids"][1].startswith("q:")
        ws.send_json({"type": "playback_finished", "turn_id": "stale-id"})  # ignored
        ws.send_json({"type": "playback_finished", "turn_id": play["turn_id"]})
        st, _ = recv_until("state"); assert st["state"] == "listening"

        # vague answer -> exactly one follow-up (streamed)
        ws.send_json({"type": "answer_text", "turn_id": str(uuid.uuid4()), "text": "it works well"})
        _, seen = recv_until("examiner_text")
        fu, _ = recv_until("tts_start"); assert fu["format"] == "pcm_s16le"
        recv_until("tts_chunk"); end, _ = recv_until("tts_end")
        ws.send_json({"type": "playback_finished", "turn_id": end["turn_id"]})
        recv_until("state")
        # second vague answer -> NO second follow-up, moves to question 2
        ws.send_json({"type": "answer_text", "turn_id": str(uuid.uuid4()), "text": "still vague"})
        q2, seen = recv_until("play_cached")
        assert q2["audio_ids"] == [f"q:{body['questions'][1]['session_question_id']}"]
        assert not any(m["type"] == "examiner_text" for m in seen)
        ws.send_json({"type": "playback_finished", "turn_id": q2["turn_id"]}); recv_until("state")

        # repeat request -> same question, follow-up not consumed
        ws.send_json({"type": "answer_text", "turn_id": str(uuid.uuid4()), "text": "can you repeat the question"})
        rep, _ = recv_until("play_cached"); assert rep["audio_ids"] == q2["audio_ids"]
        ws.send_json({"type": "playback_finished", "turn_id": rep["turn_id"]}); recv_until("state")

        # spoken answer (audio path), clear -> question 3
        import base64
        ws.send_json({"type": "answer_audio", "turn_id": str(uuid.uuid4()), "mime": "audio/wav", "duration_ms": 4000,
                      "client_silence_to_send_ms": 1400, "data": base64.b64encode(b"RIFFfake").decode()})
        tr, _ = recv_until("transcript"); assert "qdrant" in tr["text"]
        q3, _ = recv_until("play_cached")
        ws.send_json({"type": "playback_finished", "turn_id": q3["turn_id"]}); recv_until("state")

        # barge-in on the examiner then answer
        ws.send_json({"type": "answer_text", "turn_id": str(uuid.uuid4()), "text": "Qdrant gave us filtering by document id"})
        closing, _ = recv_until("play_cached"); assert closing["audio_ids"] == ["closing"]
        ws.send_json({"type": "playback_finished", "turn_id": closing["turn_id"]})
        ended = None
        for _ in range(10):
            m = ws.receive_json()
            if m["type"] == "state" and m["state"] == "ended":
                ended = m; break
        assert ended

    for _ in range(50):
        rep = client.get(f"/api/sessions/{sid}/report", headers=H).json()
        if rep["status"] in ("ready", "failed"):
            break
        time.sleep(0.1)
    assert rep["status"] == "ready", rep
    assert rep["overall_score"] == 65 and rep["band"] == "developing"   # round(mean(4,3,4,2)*20)
    assert rep["progress"] == {"done": 3, "total": 3}
    q1 = rep["questions"][0]
    assert q1["transcript"]["followup"] and q1["transcript"]["followup_answer"] and q1["question_score"] == 65

    hist = client.get("/api/sessions", headers=H).json()
    assert hist[0]["id"] == sid and hist[0]["overall_score"] == 65
    detail = client.get(f"/api/sessions/{sid}", headers=H).json()
    assert any(t["kind"] == "followup" for t in detail["turns"]) and detail["questions"][0]["audio_url"]
    assert client.get(f"/api/sessions/{sid}", headers=OTHER).status_code == 404
    assert client.get("/api/metrics", headers=H).json()["stt_ms"]["n"] >= 1

    # WebSocket for someone else's session is refused
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/call/{sid}?token=garbage") as bad:
            bad.receive_json()

    # delete cascade
    assert client.delete(f"/api/sessions/{sid}", headers=H).status_code == 204
    assert client.delete(f"/api/documents/{doc_id}", headers=H).status_code == 204
    assert client.get(f"/api/documents/{doc_id}", headers=H).status_code == 404


def test_resume_replays_current_question(client):
    r = client.post("/api/documents", headers=H, files={"file": ("r2.docx", make_docx(), "application/octet-stream")})
    doc_id = r.json()["document_id"]; wait_ready(client, doc_id)
    questions = client.post(f"/api/documents/{doc_id}/questions", headers=H, json={"n": 2}).json()["questions"]
    sid = client.post("/api/sessions", headers=H, json={"document_id": doc_id, "question_ids": [q["id"] for q in questions]}).json()["session_id"]
    with client.websocket_connect(ws_path(client, sid)) as ws:
        ws.send_json({"type": "start"})
        while ws.receive_json()["type"] != "play_cached":
            pass
    with client.websocket_connect(ws_path(client, sid)) as ws:  # reconnect
        ws.send_json({"type": "start"})
        msgs = []
        while True:
            m = ws.receive_json(); msgs.append(m)
            if m["type"] == "play_cached":
                break
        assert msgs[-1]["audio_ids"][0].startswith("q:") and "greeting" not in msgs[-1]["audio_ids"]


def test_interview_mode(client, monkeypatch):
    """mode=interview is stored on upload, drives the question prompt and is exposed on the session."""
    from app.services import question_gen
    seen = {}
    orig = question_gen.chat_json

    async def spy(**kw):
        seen["prompt"] = kw["user"]
        return await orig(**kw)

    monkeypatch.setattr(question_gen, "chat_json", spy)
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    r = client.post("/api/documents", headers=H, data={"mode": "interview"}, files={"file": ("cv.docx", make_docx(), docx_mime)})
    doc_id = r.json()["document_id"]
    assert wait_ready(client, doc_id)["mode"] == "interview"
    qs = client.post(f"/api/documents/{doc_id}/questions", headers=H, json={"n": 3}).json()["questions"]
    assert "job interview" in seen["prompt"] or "interviewer" in seen["prompt"]
    sc = client.post("/api/sessions", headers=H, json={"document_id": doc_id, "question_ids": [q["id"] for q in qs]}).json()
    assert sc["mode"] == "interview"
    assert client.get(f"/api/sessions/{sc['session_id']}", headers=H).json()["mode"] == "interview"
    # unknown modes fall back to viva
    r = client.post("/api/documents", headers=H, data={"mode": "bogus"}, files={"file": ("a.docx", make_docx(), docx_mime)})
    assert wait_ready(client, r.json()["document_id"])["mode"] == "viva"


def test_startup_warmup_is_safe_and_caches_probe_vectors(client):
    """The background warm-up must never raise, and must leave the fixed search phrases embedded for both modes."""
    from app.services import question_gen, warmup
    client.portal.call(warmup.run)
    assert {"viva", "interview"} <= set(question_gen._PROBE_VECS)
    assert all(len(v) == 5 for v in question_gen._PROBE_VECS.values())  # one vector per search phrase
