import hashlib
import os
import pathlib
import sys

DB = pathlib.Path(__file__).parent / "test.db"
if DB.exists():
    DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB}"
os.environ["QDRANT_URL"] = ""
os.environ["GROQ_API_KEY"] = "test"
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest  # noqa: E402


def fake_vec(text: str) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    return [((h[i % 32] / 255.0) - 0.5) + 0.01 for i in range(384)]


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.services import embeddings
    embeddings._embed_sync = lambda texts: [fake_vec(t) for t in texts]
    from app.main import app
    with TestClient(app) as c:
        yield c
