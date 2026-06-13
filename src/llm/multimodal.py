"""Real ``VisionLLM`` — wrap text+image messages and enforce structured output.

OWNER: Person A
SPRINT CONCEPTS:
    - Sprint 1: multimodal Chat Completion API; one endpoint, image+text content.
CONSUMES: ``OpenRouterClient`` (text gateway), ``tools.image_utils`` (resize).
PROVIDES: ``encode_image_to_data_url``, ``vision_message``, ``OpenRouterVision``.

WHY YOU CARE
------------
Four of the five specialist agents (visual, ux, accessibility, brand) call
this file, not openrouter_client.py. The vision API and the text API are
the SAME endpoint — only the user content shape changes. That is why
``OpenRouterVision`` *composes* ``OpenRouterClient`` rather than inherits.
Composition over inheritance — every time.

LOGIC OUTLINE
-------------
1. ``encode_image_to_data_url`` reads bytes, infers mime, returns
   ``data:image/png;base64,...``.
2. ``vision_message`` builds the OpenAI messages payload:
   ``[{"role":"user","content":[{"type":"text",...}, {"type":"image_url",...}]}]``.
3. ``OpenRouterVision.analyze`` resizes images, encodes them, and calls
   the OpenRouter SDK (via ``OpenRouterClient._client()``) with
   ``response_format`` derived from the schema.

DEFINITION OF DONE
------------------
[ ] ``encode_image_to_data_url(path)`` works for .png, .jpg, .webp.
[ ] ``vision_message(prompt, [img1, img2])`` returns a valid OpenAI payload
    you can paste into the playground and have it respond.
[ ] ``OpenRouterVision.analyze`` returns a validated VisualAnalysis on the
    bundled sample image (with key set).
[ ] Token count for a 4K screenshot is < 1000 after resize (verify by
    reading ``response.usage.prompt_tokens``).

DO NOT
------
- Do not concatenate ``system`` into ``user``. It works, but pollutes
  LangSmith traces and breaks the cache key.
- Do not pass > 2 images directly. Use ``side_by_side`` to make ONE.
- Do not skip the resize. Costs 3x for nothing.
- Do not set ``response_format`` to a Pydantic class — pass the schema dict.

COST DISCIPLINE
---------------
A 4K screenshot is ~2400 tokens. Resized to 1024 px max side, it is ~700.
Always resize. The ``side_by_side`` helper in ``tools.image_utils`` lets
you pack four references into one image — one upload, one charge, four
comparisons.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.config import settings
from src.contracts import VisionLLM  # noqa: F401  — declared for clarity
from src.llm.openrouter_client import OpenRouterClient
from src.utils.logger import get_logger

log = get_logger(__name__)


def encode_image_to_data_url(path: Path | str) -> str:
    """Read an image file and return ``data:image/<fmt>;base64,...``.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the suffix is not in the supported set.
    """
    # HINT: supported = {".png", ".jpg", ".jpeg", ".webp"}. Anything else
    # we either reject or pre-convert via PIL — pick one and document it
    # in the docstring above.
    #
    # TODO(person-a): five lines:
    #   import base64, mimetypes
    #   p = Path(path)
    #   if not p.exists(): raise FileNotFoundError(p)
    #   mime = mimetypes.guess_type(p.name)[0] or "image/png"
    #   b64 = base64.b64encode(p.read_bytes()).decode()
    #   return f"data:{mime};base64,{b64}"
    #
    # HINT: use ``tools.image_utils.resize_max_side`` BEFORE encoding:
    #     img = load_image(p); img = resize_max_side(img, 1024); return to_data_url(img)
    # That keeps token cost predictable.
    raise NotImplementedError("Person A: implement encode_image_to_data_url")


def vision_message(prompt: str, images: list[Path | str]) -> list[dict[str, Any]]:
    """Build the OpenAI ``messages`` payload for one user turn with N images.

    Returns a list with a SINGLE ``user`` message whose ``content`` is an
    interleaved list of ``{"type":"text",...}`` and ``{"type":"image_url",...}``
    parts.

    Example shape (what the SDK expects):
        [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
            ]}
        ]
    """
    # LOGIC: text part first, image parts after. Some providers order-sensitive
    # to the text-before-image convention; do not swap.
    #
    # HINT: list-comp + spread:
    #   parts = [{"type": "text", "text": prompt}]
    #   for img in images:
    #       url = img if isinstance(img, str) and img.startswith("data:") else encode_image_to_data_url(img)
    #       parts.append({"type": "image_url", "image_url": {"url": url}})
    #   return [{"role": "user", "content": parts}]
    # TODO(person-a): build and return the messages list.
    raise NotImplementedError("Person A: implement vision_message")


class OpenRouterVision:
    """Real ``VisionLLM`` — composes ``OpenRouterClient`` with image plumbing."""

    def __init__(self, llm: OpenRouterClient | None = None) -> None:
        # NOTE: we accept an existing client so the cost cache stays warm
        # across vision and text calls in the same process.
        self.llm = llm or OpenRouterClient()

    def analyze(
        self,
        *,
        system: str,
        user: str,
        images: list[Path | str],
        schema: type[BaseModel],
        model: str | None = None,
    ) -> BaseModel:
        """Run a multimodal completion that MUST validate against ``schema``.

        Args:
            system: System prompt.
            user: User text accompanying the image(s).
            images: 1+ image paths or data URIs.
            schema: Pydantic schema to enforce.
            model: Optional vision-capable model id; default from settings.

        Returns:
            A validated instance of ``schema``.
        """
        # HINT: the seven-step recipe:
        #   1. if not images: raise ValueError("VisionLLM.analyze requires at least one image")
        #   2. (optional, len(images) > 2): composite via tools.image_utils.side_by_side([...])
        #   3. data_urls = [encode_image_to_data_url(img) for img in images]
        #   4. messages = [{"role":"system","content":system}, *vision_message(user, data_urls)]
        #   5. rf = OpenRouterClient._schema_payload(schema)
        #   6. resp = self.llm._client().chat.completions.create(
        #          model=model or settings.default_vision_model,
        #          messages=messages,
        #          response_format=rf,
        #          max_tokens=settings.default_max_tokens,
        #      )
        #   7. return schema.model_validate_json(resp.choices[0].message.content)
        #
        # HINT: gpt-4o-mini handles up to 2048-px max side comfortably.
        # claude-3.5-sonnet is fine with 1568. Default 1024 is universal.
        #
        # HINT: wrap with ``cost.cached`` once that lands.
        #
        # NOTE: we deliberately ignore ``temperature`` here. Vision tasks
        # benefit from determinism; pin it inside _client().
        _ = model or settings.default_vision_model
        # TODO(person-a): implement steps 1–7 above (~15 lines).
        raise NotImplementedError("Person A: implement OpenRouterVision.analyze")
