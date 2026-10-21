"""Live decision step (SPEC 10.2): clear / vague / repeat_request. Never raises: worst case it returns 'clear'."""
import asyncio

from pydantic import ValidationError

from ..config import settings
from ..logging_utils import log_stage
from ..schemas import Verdict
from .groq_client import LLMError, chat_json
from .modes import get_mode
from .prompts import esc, fill, load

SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["clear", "vague", "repeat_request"]},
                   "followup": {"type": ["string", "null"]}, "reason": {"type": "string"}},
    "required": ["verdict", "followup", "reason"], "additionalProperties": False,
}
DEFAULT_FOLLOWUP = "Could you give me a specific reason or an example to support that?"


def _normalise(v: Verdict) -> Verdict:
    if v.verdict == "vague":
        f = (v.followup or "").strip() or DEFAULT_FOLLOWUP
        words = f.split()
        if len(words) > 40:
            f = " ".join(words[:40]).rstrip(",;:") + "?"
        return Verdict(verdict="vague", followup=f, reason=v.reason)
    return Verdict(verdict=v.verdict, followup=None, reason=v.reason)


async def decide(question: str, key_points: list[str], passages: list[str], answer: str,
                 session_id=None, turn_id=None, mode: str = "viva") -> Verdict:
    ps = [esc(p[:800]) for p in passages[:2]] + ["", ""]
    prompt = fill(load("decision"), question=question, key_points="; ".join(key_points),
                  passages=f"<passage>{ps[0]}</passage>\n<passage>{ps[1]}</passage>", answer=esc(answer[:1200]),
                  examiner=get_mode(mode)["examiner"], person=get_mode(mode)["person"])
    for model in (settings.MODEL_DECISION, settings.MODEL_DECISION_FALLBACK):
        try:
            raw = await chat_json(
                model=model, user=prompt, schema=SCHEMA, schema_name="viva_decision", strict=True, temperature=0,
                max_tokens=200, reasoning_effort="low", stage="decision", session_id=session_id, turn_id=turn_id)
            return _normalise(Verdict.model_validate(raw))
        except (LLMError, ValidationError, asyncio.TimeoutError) as e:
            log_stage(session_id, turn_id, "decision_failed", None, model=model, error=type(e).__name__)
    log_stage(session_id, turn_id, "decision_default_clear")
    return Verdict(verdict="clear", followup=None, reason="model unavailable")
