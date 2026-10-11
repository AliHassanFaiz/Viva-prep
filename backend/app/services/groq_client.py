"""AsyncGroq wrapper: timeout, 429 retry (honours retry-after, max 5 s, 3 tries), timing, token accounting,
and a graceful degrade ladder when a model rejects strict schemas or reasoning_effort."""
import asyncio
import json
import re
import time
from typing import Any

import groq
from groq import AsyncGroq

from ..config import settings
from ..logging_utils import log_stage, logger
from .token_budget import budget

_client: AsyncGroq | None = None


class LLMError(Exception):
    pass


def client() -> AsyncGroq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise LLMError("GROQ_API_KEY is not set.")
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY, max_retries=0, timeout=settings.LLM_TIMEOUT_S + 5)
    return _client


def _retry_after(e: Exception) -> float:
    try:
        v = e.response.headers.get("retry-after")  # type: ignore[attr-defined]
        return float(v) if v else 1.5
    except Exception:
        return 1.5


async def _with_retry(factory, timeout: float, stage: str, session_id=None, turn_id=None, model: str = ""):
    """Run factory() with timeout and 429 retries. Returns (result, elapsed_ms)."""
    last: Exception | None = None
    for attempt in range(3):
        t0 = time.perf_counter()
        try:
            res = await asyncio.wait_for(factory(), timeout=timeout)
            ms = (time.perf_counter() - t0) * 1000
            log_stage(session_id, turn_id, stage, ms, model=model, attempt=attempt + 1)
            return res, ms
        except groq.RateLimitError as e:
            last = e
            wait = min(_retry_after(e), 5.0)
            log_stage(session_id, turn_id, f"{stage}_429", None, wait_s=wait)
            await asyncio.sleep(wait)
        except asyncio.TimeoutError as e:
            last = e
            log_stage(session_id, turn_id, f"{stage}_timeout", timeout * 1000)
            if attempt >= 1:
                break
        except (groq.APIConnectionError, groq.InternalServerError) as e:
            last = e
            await asyncio.sleep(0.5)
    raise LLMError(f"{stage} failed: {type(last).__name__}")


def parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            return json.loads(text[s:e + 1])
        raise


async def chat_json(*, model: str, system: str | None = None, user: str, schema: dict, schema_name: str,
                    strict: bool, temperature: float, max_tokens: int, reasoning_effort: str | None = None,
                    stage: str, session_id=None, turn_id=None, timeout: float | None = None,
                    use_budget: bool = False) -> dict:
    """Returns the parsed JSON object. Raises LLMError on failure."""
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    timeout = timeout or settings.LLM_TIMEOUT_S
    if use_budget:
        from .token_budget import estimate_tokens
        await budget.acquire(model, estimate_tokens(system or "", user) + max_tokens)

    # attempt 0: strict/regular json_schema + reasoning_effort; attempt 1: plain json_object with schema in prompt
    ladder = [
        {"response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "strict": strict, "schema": schema}},
         "extra": {"reasoning_effort": reasoning_effort} if reasoning_effort else {}, "messages": messages},
        {"response_format": {"type": "json_object"}, "extra": {},
         "messages": messages[:-1] + [{"role": "user", "content": user + "\n\nReturn ONLY a JSON object matching this JSON schema:\n"
                                       + json.dumps(schema)}]},
    ]
    last_err: Exception | None = None
    for step in ladder:
        async def call(step=step):
            return await client().chat.completions.create(
                model=model, messages=step["messages"], temperature=temperature, max_completion_tokens=max_tokens,
                response_format=step["response_format"], extra_body=step["extra"] or None)
        try:
            resp, _ = await _with_retry(call, timeout, stage, session_id, turn_id, model)
        except groq.BadRequestError as e:  # schema/param rejected by this model -> degrade
            last_err = e
            logger.warning('{"stage":"%s_degrade","model":"%s"}', stage, model)
            continue
        except groq.APIStatusError as e:
            raise LLMError(f"{stage} failed: HTTP {e.status_code}")
        try:
            if resp.usage:
                budget.record(model, resp.usage.total_tokens or 0)
            return parse_json(resp.choices[0].message.content or "")
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            last_err = e
            continue
    raise LLMError(f"{stage} failed: {type(last_err).__name__}")
