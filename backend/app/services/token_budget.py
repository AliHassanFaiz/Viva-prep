"""60-second sliding window of tokens per model (SPEC section 11)."""
import asyncio
import time
from collections import defaultdict, deque

from ..config import settings


class TokenBudget:
    def __init__(self, budget: int | None = None):
        self.budget = budget or settings.GROQ_TPM_BUDGET
        self._events: dict[str, deque[tuple[float, int]]] = defaultdict(deque)

    def _prune(self, model: str) -> int:
        q, cutoff = self._events[model], time.monotonic() - 60
        while q and q[0][0] < cutoff:
            q.popleft()
        return sum(t for _, t in q)

    def record(self, model: str, tokens: int) -> None:
        self._events[model].append((time.monotonic(), max(0, int(tokens))))

    async def acquire(self, model: str, estimate: int) -> None:
        """Sleep until `estimate` more tokens fit in the window. Never blocks forever."""
        if estimate >= self.budget:
            return  # a single call larger than the budget can never fit; let it through
        deadline = time.monotonic() + 65
        while time.monotonic() < deadline:
            used = self._prune(model)
            if used + estimate <= self.budget:
                return
            q = self._events[model]
            wait = (q[0][0] + 60 - time.monotonic()) if q else 0.5
            await asyncio.sleep(min(max(wait, 0.2) + 0.05, 5))


budget = TokenBudget()


def estimate_tokens(*texts: str) -> int:
    return int(sum(len(t) for t in texts) / 3.5) + 1
