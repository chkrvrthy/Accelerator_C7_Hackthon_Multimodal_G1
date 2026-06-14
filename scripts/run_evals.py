"""Eval runner — schema-validity over GOLDEN_CASES.

OWNER: Person A (infra), shared maintenance.
USAGE
-----
    make eval                  # against fakes by default
    USE_REAL=1 make eval       # against real OpenRouter

DEFINITION OF DONE
------------------
[ ] Prints a single overall pass-rate line judges can screenshot.
[ ] ``CACHE_DISABLED=1 USE_REAL=1 make eval`` measures real LLM behaviour
    (not cache replays) — set this for the demo number.
[ ] Exit code 0 when pass-rate >= 80 %, 1 otherwise. Useful for CI.
[ ] Per-agent failure counts surface which schema drifted.

WHY SCHEMA-VALIDITY IS ENOUGH
-----------------------------
Schema validity proves the contract holds end-to-end across the surface.
If the visual agent suddenly returns ``palette`` as a string instead of a
list, this script catches it. Free-text "LLM-as-judge" scoring is the
post-MVP stretch — replace ``schema_valid`` with a rubric score later.
"""

from __future__ import annotations

import json
import sys

from src.agents.base import build_default_deps
from src.evals import GOLDEN_CASES, aggregate, run_eval
from src.utils.logger import get_logger

log = get_logger(__name__)


def main() -> int:
    deps = build_default_deps()
    results = []
    for case in GOLDEN_CASES:
        log.info("eval: %s ...", case.name)
        results.append(run_eval(case, deps))

    summary = aggregate(results)
    # NOTE: this JSON dump is the artifact judges screenshot. Keep it stable.
    print(
        json.dumps(
            {
                "summary": summary.model_dump(),
                "results": [r.model_dump() for r in results],
            },
            indent=2,
        )
    )
    log.info(
        "eval: overall pass-rate = %.1f%% over %d cases",
        summary.overall_pass_rate * 100,
        summary.total_cases,
    )
    # HINT: 0.8 is the demo threshold. Raise to 0.95 once prompts stabilize.
    return 0 if summary.overall_pass_rate >= 0.8 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
