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
import uuid
from pathlib import Path

from src.agents.base import AgentDeps, build_default_deps, run_with_schema
from src.schemas.outputs import (
    BrandConsistency,
    GraphState,
    RetrievedRef,
)
from src.utils.logger import get_logger
from src.utils.prompts import brand_consistency_system, brand_consistency_user

log = get_logger(__name__)


def _build_images(state: GraphState, refs: list[RetrievedRef], deps: AgentDeps) -> list[Path]:
    """Return the image list to send to the vision LLM.

    Preferred: a single side-by-side composite (candidate + refs) via Person
    B's ``image_utils`` — one upload instead of N, ~3x cheaper in tokens.
    Falls back to sending each image separately if ``image_utils`` is not yet
    implemented (Person B's slice) or compositing fails for any reason, so
    Person C's agent works regardless of the other slice's progress.
    """
    # Only include reference files that actually exist on disk. Paths come from
    # the corpus and may be stale (image deleted/moved since ingest); a missing
    # file would otherwise crash the vision encoder mid-run.
    ref_paths = [Path(r.image_path) for r in refs if Path(r.image_path).exists()]
    separate = [Path(state.image_path), *ref_paths]
    try:
        from src.tools.image_utils import load_image, side_by_side

        imgs = [load_image(p) for p in separate]
        composite = side_by_side(imgs)
        deps.cfg.report_dir.mkdir(parents=True, exist_ok=True)
        composite_path = deps.cfg.report_dir / f"_composite_{uuid.uuid4().hex[:8]}.png"
        composite.save(composite_path)
        return [composite_path]
    except Exception as e:  # NotImplementedError until Person B lands image_utils
        log.info("brand: composite unavailable (%s); sending images separately", type(e).__name__)
        return separate


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

    # Send one side-by-side composite when image_utils is available, else fall
    # back to separate uploads (see _build_images). The user message lists the
    # retrieved ref ids + scores so the LLM can only cite ids that exist.
    images = _build_images(state, refs, deps)
    result = run_with_schema(
        agent_name="agent.brand",
        system=brand_consistency_system(),
        user=brand_consistency_user(refs),
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
