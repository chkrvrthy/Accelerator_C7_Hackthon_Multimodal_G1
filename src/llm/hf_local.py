"""HuggingFace local model — Sprint 2 concept claim, NOT on the demo path.

OWNER: Person A (thin stub, ~30 lines)
SPRINT CONCEPTS:
    - Sprint 2: HuggingFace transformers local model.
CONSUMES: optional ``transformers`` install (``requirements/optional-hf.txt``).
PROVIDES: ``HFLocalClient`` (implements ``LLMClient``).

WHY THIS FILE EXISTS
--------------------
The accelerator curriculum requires us to demonstrate HuggingFace usage. We
prove it by shipping a *real* ``LLMClient`` that talks to a local model — but
we DO NOT make it part of the demo critical path. OpenRouter is faster and
more reliable; this file is the "and we can also do X" slide for the judges.

DEFINITION OF DONE (concept-claim level only)
---------------------------------------------
[ ] ``import src.llm.hf_local`` works without transformers installed
    (lazy import inside method — see HINTs).
[ ] With ``pip install -r requirements/optional-hf.txt``, calling
    ``HFLocalClient().complete(...)`` returns a small valid JSON.
[ ] Failure mode (no transformers) raises a friendly install hint, not
    a cryptic ``ModuleNotFoundError`` deep in the stack.

DO NOT
------
- Do not pull torch GPU paths into this file. CPU-only is the explicit
  contract.
- Do not put this on the demo critical path. The judges grade Sprint 2 by
  *existence*, not by quality.
- Do not expand to streaming, GPU pools, or quantization. Out of scope.

POST-MVP (if you have spare time on Day 2)
------------------------------------------
- Replace ``pipeline("text-generation", ...)`` with Outlines or
  ``lm-format-enforcer`` for grammar-constrained JSON. Small models choke
  on unconstrained JSON; constrained generation fixes it.
- Add a flag to ``AgentDeps.from_env()`` that wires this client instead of
  OpenRouter for an offline demo.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from src.utils.logger import get_logger

log = get_logger(__name__)


def _extract_json(text: str) -> str:
    """Return the first balanced ``{...}`` substring in ``text``.

    Small models often wrap JSON in prose ("Here you go:\n{...}\n"). This
    helper hunts the first balanced object so ``model_validate_json`` does not
    explode on the surrounding prose.
    """
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                return text[start : i + 1]
    raise ValueError("HFLocalClient: no balanced JSON object found in model output")


class HFLocalClient:
    """``LLMClient`` backed by a local HuggingFace transformers pipeline.

    Concept-coverage file. Not used by any agent on the critical path. Stays
    completely lazy — importing this module does NOT pull torch / transformers
    into memory. The first ``.complete()`` call is what triggers download.
    """

    def __init__(self, model_id: str = "Qwen/Qwen2.5-0.5B-Instruct") -> None:
        # NOTE: 0.5B fits in CPU memory comfortably. Bigger models make this
        # file the slow path even when no agent calls it.
        self.model_id = model_id
        self._pipe: Any | None = None

    def _ensure_pipeline(self) -> Any:
        """Lazy-load the pipeline; emit a useful error if transformers is missing."""
        if self._pipe is not None:
            return self._pipe
        try:
            from transformers import pipeline  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError(
                "transformers is not installed. For Sprint 2 HuggingFace coverage:\n"
                "    pip install -r requirements/optional-hf.txt"
            ) from e
        log.info("HFLocalClient: loading %s on CPU (first call may take ~30s)", self.model_id)
        # LOGIC: device_map left as the library default (CPU on most boxes).
        # Forcing "cpu" via device_map is fine but breaks the helpful auto-
        # detection on machines with MPS / CUDA available for ad-hoc demos.
        self._pipe = pipeline("text-generation", model=self.model_id)
        return self._pipe

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: type[BaseModel],
        model: str | None = None,  # noqa: ARG002 — kept for protocol compatibility
        temperature: float | None = None,
    ) -> BaseModel:
        """Run the local model and validate JSON against ``schema``.

        Concept-claim quality only — this path is intentionally simple and
        does NOT compete with OpenRouter on accuracy.
        """
        pipe = self._ensure_pipeline()
        schema_blob = json.dumps(schema.model_json_schema())
        prompt = (
            f"<|system|>\n{system}\n"
            f"Return ONLY a JSON object matching this schema:\n{schema_blob}\n"
            f"<|user|>\n{user}\n"
            f"<|assistant|>\n"
        )
        out = pipe(
            prompt,
            max_new_tokens=512,
            do_sample=temperature is not None and temperature > 0,
            temperature=temperature or 0.0,
            return_full_text=False,
        )
        raw = out[0]["generated_text"]
        return schema.model_validate_json(_extract_json(raw))
