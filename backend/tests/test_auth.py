"""Signup / login, token handling, and that one user can never see another user's data (SQL and Qdrant)."""
import time
import uuid

import jwt
import pytest

from conftest import fake_vec
from test_flow import fakes, make_docx, wait_ready  # noqa: F401  (fakes = mocked Groq, ElevenLabs, STT)

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PW = "correct-horse-1"


def signup(client, email=None, password=PW):
    email = email or f"{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    b = r.json()
    return {"Authorization": f"Bearer {b['access_token']}"}, b["user"]["id"], email


def make_session(client, headers):
    doc = client.post("/api/documents", headers=headers, files={"file": ("r.docx", make_docx(), DOCX)}).json()["document_id"]
    assert wait_ready(client, doc, headers)["status"] == "ready"
    qs = client.post(f"/api/documents/{doc}/questions", headers=headers, json={"n": 3}).json()["questions"]
    sc = client.post("/api/sessions", headers=headers, json={"document_id": doc, "question_ids": [q["id"] for q in qs]}).json()
    return doc, sc["session_id"], qs


def test_signup_login_me(client):
    h, uid, email = signup(client)
    assert client.get("/api/auth/me", headers=h).json() == {"id": uid, "email": email}
    ok = client.post("/api/auth/login", json={"email": email.upper(), "password": PW})  # email is case-insensitive
    assert ok.status_code == 200 and ok.json()["user"]["id"] == uid
    bad = client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PW})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json()["error"]["message"] == unknown.json()["error"]["message"]  # no account enumeration
    assert client.post("/api/auth/signup", json={"email": email, "password": PW}).status_code == 409
    assert client.post("/api/auth/signup", json={"email": "x@example.com", "password": "short"}).json()["error"]["code"] == "weak_password"
    assert client.post("/api/auth/signup", json={"email": "not-an-email", "password": PW}).json()["error"]["code"] == "bad_email"


def test_password_is_not_stored_in_plain_text(client):
    from app.services.auth import hash_password_sync, verify_password_sync
    h = hash_password_sync(PW)
    assert PW not in h and h.startswith("scrypt$")
    assert verify_password_sync(PW, h) and not verify_password_sync("other", h) and not verify_password_sync(PW, None)


def test_login_throttle(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    signup(client, email)
    codes = [client.post("/api/auth/login", json={"email": email, "password": "nope-nope-1"}).status_code for _ in range(9)]
    assert codes[:8] == [401] * 8 and codes[8] == 429


def test_tokens_are_checked(client):
    h, uid, _ = signup(client)
    assert client.get("/api/sessions").status_code == 401
    assert client.get("/api/sessions", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.get("/api/sessions", headers={"Authorization": h["Authorization"][:-3] + "abc"}).status_code == 401  # tampered
    from app.services import auth
    expired = jwt.encode({"sub": uid, "typ": "access", "exp": int(time.time()) - 10}, auth._get_secret(), algorithm="HS256")
    assert client.get("/api/sessions", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    forged = jwt.encode({"sub": uid, "typ": "access", "exp": int(time.time()) + 600}, "some-other-secret", algorithm="HS256")
    assert client.get("/api/sessions", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    ws_tok = auth.create_ws_token(uuid.UUID(uid), uuid.uuid4())  # a WebSocket token is not an API token
    assert client.get("/api/sessions", headers={"Authorization": f"Bearer {ws_tok}"}).status_code == 401
    gone = auth.create_access_token(uuid.uuid4())  # valid signature, but no such user
    assert client.get("/api/sessions", headers={"Authorization": f"Bearer {gone}"}).status_code == 401


def test_users_cannot_see_each_others_data(client):
    a, _, _ = signup(client)
    b, _, _ = signup(client)
    doc, sid, qs = make_session(client, a)
    body = client.get(f"/api/sessions/{sid}", headers=a).json()
    sqid_url = body["questions"][0]["audio_url"]

    probes = [
        ("get", f"/api/documents/{doc}"), ("get", f"/api/documents/{doc}/questions"), ("post", f"/api/documents/{doc}/questions"),
        ("delete", f"/api/documents/{doc}"), ("get", f"/api/sessions/{sid}"), ("get", f"/api/sessions/{sid}/report"),
        ("post", f"/api/sessions/{sid}/end"), ("post", f"/api/sessions/{sid}/ws-token"), ("delete", f"/api/sessions/{sid}"),
        ("get", sqid_url), ("patch", f"/api/questions/{qs[0]['id']}"), ("delete", f"/api/questions/{qs[0]['id']}"),
    ]
    for method, url in probes:
        kw = {"json": {"text": "hijacked question text?"}} if method == "patch" else {}
        r = getattr(client, method)(url, headers=b, **kw)
        assert r.status_code == 404, (method, url, r.status_code)
    # B cannot start a session on A's document, and A's data is untouched
    assert client.post("/api/sessions", headers=b, json={"document_id": doc, "question_ids": [q["id"] for q in qs]}).status_code == 404
    assert client.get("/api/sessions", headers=b).json() == []
    assert len(client.get("/api/sessions", headers=a).json()) == 1
    assert client.get(f"/api/documents/{doc}", headers=a).status_code == 200


def test_qdrant_search_is_scoped_to_the_user(client):
    from app.services import qdrant_store
    a, a_id, _ = signup(client)
    _, b_id, _ = signup(client)
    doc = client.post("/api/documents", headers=a, files={"file": ("r.docx", make_docx(), DOCX)}).json()["document_id"]
    assert wait_ready(client, doc, a)["status"] == "ready"
    vec = fake_vec("methodology and design choices")
    run = client.portal.call
    assert len(run(qdrant_store.search, a_id, doc, vec, 3)) >= 1            # the owner finds their chunks
    assert run(qdrant_store.search, b_id, doc, vec, 3) == []                # another user, same document id: nothing
    assert run(qdrant_store.search, a_id, str(uuid.uuid4()), vec, 3) == []  # right user, wrong document
    with pytest.raises(ValueError):                                         # an unscoped search is refused outright
        run(qdrant_store.search, "", doc, vec, 3)
    with pytest.raises(ValueError):
        run(qdrant_store.search, a_id, "", vec, 3)


def test_websocket_tokens(client):
    from app.services import auth
    a, a_id, _ = signup(client)
    b, b_id, _ = signup(client)
    doc, sid1, _ = make_session(client, a)
    sid2 = client.post("/api/sessions", headers=a, json={"document_id": doc, "question_ids": [
        q["id"] for q in client.get(f"/api/documents/{doc}/questions", headers=a).json()["questions"]]}).json()["session_id"]

    def refused(path):
        with pytest.raises(Exception):
            with client.websocket_connect(path) as ws:
                ws.receive_json()

    refused(f"/ws/call/{sid1}")                                                                   # no token
    refused(f"/ws/call/{sid1}?token=garbage")
    refused(f"/ws/call/{sid1}?token={auth.create_access_token(uuid.UUID(a_id))}")                  # API token, wrong kind
    refused(f"/ws/call/{sid1}?token={auth.create_ws_token(uuid.UUID(b_id), uuid.UUID(sid1))}")     # someone else's session
    tok1 = client.post(f"/api/sessions/{sid1}/ws-token", headers=a).json()["token"]
    refused(f"/ws/call/{sid2}?token={tok1}")                                                       # token for a different session
    with client.websocket_connect(f"/ws/call/{sid1}?token={tok1}") as ws:                          # the right one works
        ws.send_json({"type": "start"})
        assert ws.receive_json()
