from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache
def load(name: str) -> str:
    return (_DIR / f"{name}.md").read_text(encoding="utf-8")


def fill(template: str, **values: str) -> str:
    """Placeholder substitution that tolerates braces inside the values or the template."""
    for k, v in values.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def esc(text: str) -> str:
    """Stop student speech / report text from closing our delimiter tags."""
    return (text or "").replace("</", "<\\/")
