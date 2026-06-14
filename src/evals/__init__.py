"""Eval harness — Sprint 4 concept claim. Schema-validity scoring only."""

from .golden_set import GOLDEN_CASES, GoldenCase
from .harness import EvalResult, EvalSummary, aggregate, run_eval

__all__ = ["GOLDEN_CASES", "EvalResult", "EvalSummary", "GoldenCase", "aggregate", "run_eval"]
