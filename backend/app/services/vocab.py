"""Whisper vocabulary hint: up to 25 terms, ~180 tokens max (Groq limits the prompt to 224 tokens)."""
import re
from collections import Counter

_STOP = set("""the this that with from have been were which their there these those would could should about between
through during before after because however therefore although whether within without against among using used
also other such than then them they what when where while will your more most some many much very each into over
under only both same another further results result figure table section chapter introduction conclusion abstract
""".split())
_FIRST_WORD_STOP = {"The", "This", "That", "These", "Those", "In", "On", "At", "For", "And", "But", "Our", "We", "It",
                    "As", "An", "A", "Of", "To", "By", "With", "From", "Figure", "Table", "Section", "Chapter"}
MAX_CHARS = 560  # ~180 tokens with headroom


def build_vocab_hint(text: str) -> str:
    acr = Counter(re.findall(r"\b[A-Z]{2,6}\b", text))
    acronyms = [w for w, c in acr.most_common(40) if c >= 2 and w not in {"THE", "AND", "FOR", "PDF"}]

    names = Counter()
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text):
        phrase = m.group(0)
        words = phrase.split()
        if words[0] in _FIRST_WORD_STOP:
            words = words[1:]
        if len(words) >= 2:
            names[" ".join(words)] += 1
    multi = [w for w, c in names.most_common(40) if c >= 2]

    freq = Counter(w.lower() for w in re.findall(r"\b[A-Za-z][A-Za-z\-]{6,}\b", text))
    rare = [w for w, c in freq.most_common(200) if w not in _STOP and c >= 3]

    terms: list[str] = []
    for src in (acronyms[:10], multi[:8], rare[:30]):
        for t in src:
            if t not in terms and t.lower() not in {x.lower() for x in terms}:
                terms.append(t)
            if len(terms) >= 25:
                break
        if len(terms) >= 25:
            break

    hint = ""
    for t in terms:
        candidate = (hint + ", " + t) if hint else t
        if len(f"Technical terms: {candidate}.") > MAX_CHARS:
            break
        hint = candidate
    return f"Technical terms: {hint}." if hint else ""
