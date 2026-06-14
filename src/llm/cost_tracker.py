"""Process-wide cost telemetry + a tiny circuit breaker.

OWNER: Person A
SPRINT CONCEPTS: Sprint 5 (cost optimization), Sprint 6 (resilience).

WHY THIS FILE EXISTS
--------------------
The user complaint was: "did we even build cost optimization properly?"
We had a cache on disk but no NUMBERS — no way to look at the Settings
tab and see "this run cost $0.04, the cache saved 3 calls". This file
adds two things, both deliberately tiny:

1. ``CostTracker`` — a process-wide singleton that totals input/output
   tokens, cache hits, cache misses, and per-model spend. It exposes a
   ``snapshot()`` for the UI Settings tab. Zero external deps.

2. ``CircuitBreaker`` — a session-scoped fail-fast for OpenRouter. If
   we see N hard failures (auth, quota, persistent timeout) in a row,
   subsequent calls short-circuit immediately for ``cooldown_s`` seconds
   so all 5 specialist agents do not each independently retry 3× and
   make the user wait a full minute before the error message.

The breaker is intentionally simple: a single counter and a timestamp.
This is not Hystrix. It is a fuse.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from src.utils.logger import get_logger

log = get_logger(__name__)

# Rough USD-per-million-token defaults. These are NOT a price list — they
# are anchors so the Settings tab shows "~$0.04 this run" instead of a
# meaningless "12,400 tokens". Override at runtime via ``set_pricing``.
_DEFAULT_PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    # (input, output) per million tokens. Order: cheapest → most expensive.
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "anthropic/claude-3.5-sonnet": (3.00, 15.00),
    "anthropic/claude-3.5-haiku": (0.80, 4.00),
    # Cheap default if model is unrecognised — picks GPT-4o-mini pricing.
    "_default": (0.15, 0.60),
}


@dataclass
class _RunStats:
    """One row in the per-run ledger; aggregated for the session total."""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit: bool = False

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class CostTracker:
    """Process-wide cost ledger. Thread-safe. Cheap.

    The tracker never raises. Telemetry is best-effort: a missing field
    on a provider response should not break a run.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._calls: list[_RunStats] = []
        self._pricing = dict(_DEFAULT_PRICING_USD_PER_MTOK)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def record_call(
        self,
        *,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cache_hit: bool = False,
    ) -> None:
        """Append one call to the ledger.

        Cache hits record zero tokens but bump the hit counter — that is
        what makes "cache saved N calls" visible.
        """
        try:
            row = _RunStats(
                model=model or "_unknown",
                prompt_tokens=int(prompt_tokens or 0),
                completion_tokens=int(completion_tokens or 0),
                cache_hit=bool(cache_hit),
            )
            with self._lock:
                self._calls.append(row)
        except Exception as e:  # telemetry must never crash the run
            log.debug("cost_tracker.record_call swallowed: %s", e)

    def reset(self) -> None:
        """Clear the ledger (called at the start of a UI run)."""
        with self._lock:
            self._calls.clear()

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-able summary suitable for the Settings tab.

        Shape::

            {
              "calls": 7,
              "cache_hits": 3,
              "cache_misses": 4,
              "prompt_tokens": 12400,
              "completion_tokens": 1800,
              "total_tokens": 14200,
              "estimated_usd": 0.052,
              "by_model": {
                "anthropic/claude-3.5-sonnet": {
                  "calls": 5, "tokens": 12100, "usd": 0.048
                },
                ...
              },
            }
        """
        with self._lock:
            calls = list(self._calls)

        cache_hits = sum(1 for c in calls if c.cache_hit)
        cache_misses = len(calls) - cache_hits
        prompt = sum(c.prompt_tokens for c in calls)
        completion = sum(c.completion_tokens for c in calls)

        by_model: dict[str, dict[str, float]] = {}
        for c in calls:
            row = by_model.setdefault(c.model, {"calls": 0.0, "tokens": 0.0, "usd": 0.0})
            row["calls"] += 1
            row["tokens"] += c.total_tokens
            row["usd"] += self._estimate_usd(c)

        usd = sum(row["usd"] for row in by_model.values())
        return {
            "calls": len(calls),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "estimated_usd": round(usd, 4),
            "by_model": {
                model: {
                    "calls": int(r["calls"]),
                    "tokens": int(r["tokens"]),
                    "usd": round(r["usd"], 4),
                }
                for model, r in by_model.items()
            },
        }

    def _estimate_usd(self, c: _RunStats) -> float:
        if c.cache_hit:
            return 0.0
        in_rate, out_rate = self._pricing.get(c.model, self._pricing["_default"])
        return (c.prompt_tokens / 1_000_000.0) * in_rate + (
            c.completion_tokens / 1_000_000.0
        ) * out_rate

    def set_pricing(self, model: str, *, input_per_mtok: float, output_per_mtok: float) -> None:
        """Override the default rate for a single model (for accurate telemetry)."""
        with self._lock:
            self._pricing[model] = (float(input_per_mtok), float(output_per_mtok))


# Module-level singleton — every LLM client + cache hit reports here.
_TRACKER = CostTracker()


def get_cost_tracker() -> CostTracker:
    return _TRACKER


# --------------------------------------------------------------------------- #
# Circuit breaker                                                              #
# --------------------------------------------------------------------------- #
class CircuitBreaker:
    """Tiny session-scoped circuit breaker.

    State machine:
      * CLOSED   — normal traffic flows.
      * OPEN     — last N calls failed hard; ``allow()`` returns False
                   until ``cooldown_s`` elapses.

    The breaker is keyed by ``name`` (default "openrouter") so callers can
    have one breaker per upstream service if they want.

    Why we need this: without it, a missing API key triggers 5 specialist
    agents × 3 retries = 15 round-trip waits before the user sees the
    failure. With it, the first agent's hard failure trips the breaker;
    subsequent agents see ``allow() == False`` and fail instantly.
    """

    def __init__(self, *, threshold: int = 2, cooldown_s: float = 30.0) -> None:
        self.threshold = max(1, int(threshold))
        self.cooldown_s = float(cooldown_s)
        self._lock = threading.Lock()
        self._fails = 0
        self._opened_at: float | None = None
        self._last_reason = ""

    def allow(self) -> bool:
        """Return True if the next call should proceed; False if short-circuited."""
        with self._lock:
            if self._opened_at is None:
                return True
            if (time.monotonic() - self._opened_at) >= self.cooldown_s:
                # LOGIC: cooldown elapsed → half-open. Reset and let one
                # call try; if it fails again, the breaker re-opens.
                self._opened_at = None
                self._fails = 0
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._fails = 0
            self._opened_at = None

    def record_failure(self, reason: str = "") -> None:
        with self._lock:
            self._fails += 1
            self._last_reason = reason
            if self._fails >= self.threshold:
                self._opened_at = time.monotonic()
                log.warning(
                    "circuit_breaker: OPEN after %d failures (last=%s); " "fast-failing for %.0fs",
                    self._fails,
                    reason or "unknown",
                    self.cooldown_s,
                )

    def state(self) -> dict[str, Any]:
        """Snapshot for the Settings tab."""
        with self._lock:
            is_open = self._opened_at is not None
            remaining = (
                max(0.0, self.cooldown_s - (time.monotonic() - self._opened_at))
                if is_open and self._opened_at is not None
                else 0.0
            )
            return {
                "state": "open" if is_open else "closed",
                "fails": self._fails,
                "threshold": self.threshold,
                "cooldown_s": self.cooldown_s,
                "remaining_s": round(remaining, 1),
                "last_reason": self._last_reason,
            }


_BREAKERS: dict[str, CircuitBreaker] = {}
_BREAKERS_LOCK = threading.Lock()


def get_circuit_breaker(name: str = "openrouter") -> CircuitBreaker:
    """Return (or lazily create) the named breaker."""
    with _BREAKERS_LOCK:
        cb = _BREAKERS.get(name)
        if cb is None:
            cb = _BREAKERS[name] = CircuitBreaker()
        return cb


class CircuitOpenError(RuntimeError):
    """Raised by the OpenRouter client when the breaker is open.

    Carries enough context for the agent layer to render a helpful error
    in the UI ("OpenRouter is unreachable; retry in N seconds").
    """

    def __init__(self, breaker: CircuitBreaker) -> None:
        s = breaker.state()
        msg = (
            f"circuit open ({s['fails']}/{s['threshold']} failures, "
            f"last={s['last_reason'] or 'unknown'}, retry in ~{s['remaining_s']:.0f}s)"
        )
        super().__init__(msg)
        self.state = s
