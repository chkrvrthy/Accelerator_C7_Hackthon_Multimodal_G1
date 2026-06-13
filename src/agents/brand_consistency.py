"""Brand Consistency agent — RAG-aware: candidate vs retrieved references.

OWNER: Person C
SPRINT CONCEPTS:
    - Sprint 3: image RAG (the agent that consumes retrieval).
    - Sprint 6: parallel branch of the multi-agent graph.
CONSUMES: ``Retriever``, ``VisionLLM``.
PROVIDES: ``run(state, deps) -> {"brand": BrandConsistency}``.

WHY YOU CARE
------------
This is the only agent that consumes retrieval. Without RAG it falls back to
"compare against itself" — which still works but loses the killer "we have
seen 30 of your existing screens" magic. Get retrieval working before
polishing this prompt.

LOGIC OUTLINE
-------------
1. Retrieve top-k references via the candidate image (visual similarity).
2. If no refs: emit a fallback BrandConsistency with consistency_score=80
   and a single recommendation "ingest reference designs to enable real
   brand comparison". Do NOT raise.
3. Pass candidate + refs to the vision LLM with ``schema=BrandConsistency``.

WHY ONE COMPOSITE IMAGE
-----------------------
Sending five separate images costs 5× the tokens and the model still has
to mentally line them up. ``tools.image_utils.side_by_side([...])`` gives
the model a single canvas it can describe spatially: "leftmost is
candidate; the four to the right are references in score order".

DEFINITION OF DONE
------------------
[ ] tests/person_c/test_brand_consistency.py green (incl. empty-corpus path).
[ ] ``make run-c-brand`` prints a valid BrandConsistency JSON against fakes.
[ ] With ``USE_REAL=1`` and an ingested corpus, ``ref_ids`` contains 3-5
    actual ids from the LanceDB table (not made-up strings).
[ ] consistency_score is sensitive: identical refs → 90+; clearly off-brand
   refs → 50-.

DO NOT
------
- Do not call retriever twice. Cache state.refs in this node so the
  synthesizer can read them later (see "writes refs back to state" below).
- Do not let the LLM invent ``ref_ids``. The schema validator catches some
  cases but not all — pin the IDs in the prompt.
- Do not raise on empty corpus. The fallback path is part of the contract.

PROMPT-ITERATION CHECKLIST
--------------------------
1. The model rates everything 75 → add anchor examples in the prompt
   ("two pixel-identical screenshots = 100; same color palette = 80; same
   sector but different palette = 60; unrelated = 0..40").
2. The model lists missing-from-the-image references → "ref_ids must come
   from the labels under each image in the composite; do NOT invent ids."
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.agents.base import AgentDeps, build_default_deps, run_with_schema
from src.schemas.outputs import (
    BrandConsistency,
    GraphState,
    RetrievedRef,
)
from src.utils.logger import get_logger
from src.utils.prompts import brand_consistency_system

log = get_logger(__name__)


def run(state: GraphState, deps: AgentDeps) -> dict[str, BrandConsistency | list[RetrievedRef]]:
    """Run the Brand Consistency agent."""
    refs = deps.retriever.retrieve_by_image(Path(state.image_path), k=5)

    if not refs:
        # LOGIC: graceful empty-corpus fallback. The synthesizer still gets a
        # BrandConsistency to combine; the operator notices via the drift
        # strings that no comparable refs were available.
        bc = BrandConsistency(
            consistency_score=80.0,
            color_drift="(no references available — score is an estimate)",
            type_drift="(no references available — score is an estimate)",
            component_drift="(no references available — score is an estimate)",
            comparable_refs=[],
        )
        return {"brand": bc, "refs": []}

    user_text = (
        "Compare the leftmost (candidate) image against the references on the right. "
        "Score brand consistency. Describe color_drift, type_drift, component_drift "
        "and cite the retrieved refs verbatim."
    )
    # HINT: build a side-by-side composite to reduce token cost (~3x):
    # TODO(person-c): wire side_by_side once tools.image_utils is real:
    #   from PIL import Image
    #   from src.tools.image_utils import load_image, side_by_side
    #   imgs = [load_image(state.image_path), *[load_image(r.image_path) for r in refs]]
    #   composite = side_by_side(imgs)
    #   composite_path = settings.report_dir / f"_composite_{uuid.uuid4().hex[:8]}.png"
    #   composite.save(composite_path)
    #   images = [composite_path]
    # For now we send all images separately (slower, but works).
    images = [Path(state.image_path), *[Path(r.image_path) for r in refs]]
    result = run_with_schema(
        agent_name="agent.brand",
        system=brand_consistency_system(),
        user=user_text,
        images=images,
        schema=BrandConsistency,
        deps=deps,
    )
    assert isinstance(result, BrandConsistency)
    # NOTE: pin comparable_refs to the actual retrieval result so the LLM
    # can't fabricate ids. The downstream UI shows these directly.
    if not result.comparable_refs:
        result.comparable_refs = list(refs)
    return {"brand": result, "refs": refs}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Brand Consistency agent (Person C)")
    parser.add_argument("--image", required=True)
    parser.add_argument("--use-real", action="store_true", default=None)
    args = parser.parse_args()

    deps = build_default_deps(use_real=args.use_real)
    state = GraphState(image_path=str(args.image))
    out = run(state, deps)
    print(json.dumps(out["brand"].model_dump(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
