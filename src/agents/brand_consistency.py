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
from src.utils.prompts import (
    brand_consistency_system,
    brand_consistency_user,
    multi_image_note,
)

log = get_logger(__name__)


def _retrieve_for_all_frames(state: GraphState, deps: AgentDeps) -> list[RetrievedRef]:
    """Retrieve top-k for each frame, dedupe by id (keeping max score), top-5 global.

    Single-frame runs (the historical case) reduce to one retrieve_by_image
    call — same behaviour as before. Multi-frame runs amortize one
    retrieve per frame and merge; the cost is dominated by CLIP encoding
    which is already cached per image inside the embedder.

    Per-frame attribution: every kept ref records the set of
    ``frame_labels`` whose query surfaced it in the top-k. Used by the
    brand prompt to phrase drift findings against specific screens
    ("Pricing matched stripe-pricing-2024 at 0.83; Hero did not").
    """
    by_id: dict[str, RetrievedRef] = {}
    n_frames = len(state.image_paths)
    for i, path in enumerate(state.image_paths):
        # Use the canonical label when present; the GraphState validator
        # has already padded short label lists with filename stems so
        # ``state.frame_labels[i]`` always exists by this point.
        frame_label = (
            state.frame_labels[i] if i < len(state.frame_labels) else f"Frame {i + 1}"
        )
        try:
            hits = deps.retriever.retrieve_by_image(Path(path), k=5)
        except Exception as e:
            # LOGIC: a single bad frame (missing file, encoder hiccup) must
            # not kill the whole retrieval pass — log and skip so the LLM
            # still gets refs from the remaining frames.
            log.warning(
                "brand: retrieve_by_image failed for %s (%s); skipping that frame",
                path,
                type(e).__name__,
            )
            continue
        for ref in hits:
            existing = by_id.get(ref.id)
            if existing is None:
                # New ref — clone with this frame attributed (only when
                # the run is multi-frame; for N=1 we keep matched_frames
                # empty so the legacy single-frame contract is unchanged).
                ref_copy = ref.model_copy(deep=True)
                ref_copy.matched_frames = [frame_label] if n_frames > 1 else []
                by_id[ref.id] = ref_copy
            else:
                # Same ref surfaced by another frame — extend attribution
                # and keep the BEST score across frames.
                if n_frames > 1 and frame_label not in existing.matched_frames:
                    existing.matched_frames.append(frame_label)
                if ref.score > existing.score:
                    existing.score = ref.score
    return sorted(by_id.values(), key=lambda r: r.score, reverse=True)[:5]


def _build_images(state: GraphState, refs: list[RetrievedRef], deps: AgentDeps) -> list[Path]:
    """Return the image list to send to the vision LLM.

    Preferred: a single side-by-side composite (candidate + refs) via Person
    B's ``image_utils`` — one upload instead of N, ~3x cheaper in tokens.
    Falls back to sending each image separately if ``image_utils`` is not yet
    implemented (Person B's slice) or compositing fails for any reason, so
    Person C's agent works regardless of the other slice's progress.
    """
    # Include every uploaded candidate frame plus every reference file
    # that actually exists on disk. Refs that point at stale paths (image
    # deleted/moved since ingest) are dropped silently so the vision
    # encoder never crashes mid-run on a missing file.
    candidate_paths = [Path(p) for p in state.image_paths]
    ref_paths = [Path(r.image_path) for r in refs if Path(r.image_path).exists()]
    separate = [*candidate_paths, *ref_paths]
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
    """Run the Brand Consistency agent.

    MULTI-FRAME RETRIEVAL
    ---------------------
    For comparison-mode runs (N>1), we retrieve top-k references from
    EVERY frame and dedupe by ref id, keeping the highest score per id.
    A site's hero, dashboard, and pricing pages embed to different
    regions of CLIP space, so retrieving from only the primary frame
    would miss refs that match the others. We then take the global
    top-5 by score, regardless of which frame surfaced them.
    """
    refs = _retrieve_for_all_frames(state, deps)

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
    user_text = brand_consistency_user(refs) + multi_image_note(
        len(state.image_paths), state.frame_labels
    )
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
