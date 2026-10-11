"""Question audio cache: in memory plus a temp directory, keyed by session_question_id."""
import shutil
import tempfile
from pathlib import Path

_DIR = Path(tempfile.gettempdir()) / "viva_prep_audio"
_DIR.mkdir(parents=True, exist_ok=True)
_mem: dict[str, bytes] = {}


def save(key: str, data: bytes) -> None:
    _mem[key] = data
    try:
        (_DIR / f"{key}.mp3").write_bytes(data)
    except OSError:
        pass


def get(key: str) -> bytes | None:
    if key in _mem:
        return _mem[key]
    p = _DIR / f"{key}.mp3"
    if p.exists():
        data = p.read_bytes()
        _mem[key] = data
        return data
    return None


def delete(key: str) -> None:
    _mem.pop(key, None)
    try:
        (_DIR / f"{key}.mp3").unlink(missing_ok=True)
    except OSError:
        pass


def clear_all() -> None:
    _mem.clear()
    shutil.rmtree(_DIR, ignore_errors=True)
    _DIR.mkdir(parents=True, exist_ok=True)
