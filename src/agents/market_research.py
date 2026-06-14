"""Market Research agent — tool-augmented (web search + LLM synthesis).

OWNER: Person E
SPRINT CONCEPTS:
    - Sprint 5: tool augmentation (search), structured output.
    - Sprint 6: parallel branch of the multi-agent graph.
CONSUMES: ``WebSearch``, ``LLMClient`` (text-only — no image needed).
PROVIDES: ``run(state, deps) -> {"market": MarketResearch}``.

WHY YOU CARE
------------
This is the only agent on the critical path that uses a *tool* (web search).
Without it, "Sprint 5 tool-augmented agent" is unfilled. It is also the only
agent that doesn't need an image — pure text in, structured text out.

LOGIC OUTLINE
-------------
1. Build a query from ``state.instructions`` (or "design competitors" if
   absent — graceful default).
2. Call ``deps.search.search(query, k=5)`` → list of SearchResult.
3. Pass the search context as text to the LLM with schema=MarketResearch.
4. Return ``{"market": ...}``.

DEFINITION OF DONE
------------------
[ ] tests/person_e/test_market_research.py green against fake_deps.
[ ] ``make run-e-market`` prints a valid MarketResearch JSON.
[ ] ``competitors`` always has 3-5 entries with non-empty ``name`` AND ``url``.
[ ] ``trend_summary`` is grounded in the search snippets — quote a phrase
    verbatim from snippets in the prompt and require the model to use it
    (or say "not in snippets").
[ ] With ``USE_REAL=1`` and Tavily, the URLs in competitors are clickable
    and lead to real product pages.

DO NOT
------
- Do not let the LLM cite competitors that are NOT in the search results.
  The prompt must say "ONLY use names that appear in <snippets>".
- Do not pass full HTML pages — pass the snippet field only.
- Do not call search twice for the same query in one run.

PROMPT-ITERATION CHECKLIST
--------------------------
1. Hallucinated URLs → "url MUST be copied verbatim from <results>; if you
   cannot find it, omit the competitor."
2. Vague trends ("fintech is growing") → "trend_summary must reference
   a specific UI pattern visible in the snippets (e.g., 'tabbed sidebar')."
3. Empty research_queries → "list 3 follow-up Google queries the team
   should run; phrase them as Google searches, not full sentences."
"""

from __future__ import annotations

import argparse
import html
import json

from src.agents.base import AgentDeps, build_default_deps, run_with_schema
from src.schemas.outputs import GraphState, MarketResearch
from src.utils.logger import get_logger
from src.utils.prompts import market_research_system

log = get_logger(__name__)


def run(state: GraphState, deps: AgentDeps) -> dict[str, MarketResearch]:
    """Run the Market Research agent."""
    query = state.instructions or "design competitors and trends"
    hits = deps.search.search(query, k=5)

    # NOTE: shape the search output as XML so the model treats it as data,
    # not as text to summarize. Same Sprint-1 pattern as the UX agent.
    snippets = "\n".join(
        "  "
        f"<result rank='{i + 1}' "
        f"title='{html.escape(h.title, quote=True)}' "
        f"url='{html.escape(h.url, quote=True)}'>"
        f"{html.escape(h.snippet)}"
        "</result>"
        for i, h in enumerate(hits)
    )
    user_text = (
        "<query>" + query + "</query>\n"
        "<results>\n" + snippets + "\n</results>\n"
        "<task>"
        "List 3-5 competitors and 3-5 trends grounded in the results. "
        "Use ONLY competitor names and URLs that appear in <results>. "
        "Copy cited URLs verbatim into citations. If the results are thin, "
        "say so through opportunities or threats instead of inventing facts."
        "</task>"
    )

    result = run_with_schema(
        agent_name="agent.market",
        system=market_research_system(),
        user=user_text,
        images=[],  # text-only call
        schema=MarketResearch,
        deps=deps,
    )
    assert isinstance(result, MarketResearch)
    return {"market": result}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Market Research agent (Person E)")
    parser.add_argument("--image", default=None, help="Accepted for Makefile symmetry; unused.")
    parser.add_argument("--instructions", default="design competitors and trends")
    parser.add_argument("--use-real", action="store_true", default=None)
    args = parser.parse_args()

    deps = build_default_deps(use_real=args.use_real)
    state = GraphState(image_path="(unused)", instructions=args.instructions)
    out = run(state, deps)
    print(json.dumps(out["market"].model_dump(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
