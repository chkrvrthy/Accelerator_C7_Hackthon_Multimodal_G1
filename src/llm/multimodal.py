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

import base64
import mimetypes
from io import BytesIO
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.config import settings
from src.llm.cost import cached
from src.llm.openrouter_client import OpenRouterClient
from src.utils.logger import get_logger

log = get_logger(__name__)

_SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
# Token-cost discipline: cap upload dimension. 1024 px max side is universal
# across providers and keeps token cost predictable (~700 tokens / image).
_MAX_IMAGE_SIDE = 1024


def encode_image_to_data_url(path: Path | str) -> str:
    """Read an image file and return ``data:image/<fmt>;base64,...``.

    The image is automatically resized so its longest side is at most
    ``_MAX_IMAGE_SIDE`` (1024 px) — keeps demo costs predictable. EXIF
    rotation is applied so phone screenshots come out upright.

    Args:
        path: Either a filesystem path OR an already-formatted ``data:`` URI
              (returned unchanged so callers can mix the two cheaply).

    Raises:
        FileNotFoundError: when the path does not exist.
        ValueError: when the suffix is not in the supported set.
    """
    # LOGIC: pass-through for already-encoded inputs. Useful when the caller
    # composited multiple references with side_by_side and wants to skip a
    # round-trip through the filesystem.
    if isinstance(path, str) and path.startswith("data:"):
        return path

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"image not found: {p}")
    if p.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise ValueError(
            f"unsupported image suffix {p.suffix!r}; supported: {sorted(_SUPPORTED_SUFFIXES)}"
        )

    # LOGIC: try the resize path first. If Pillow is missing (Person C/D
    # might run a partial install during dev), fall back to raw bytes — the
    # provider will accept it but cost more tokens. Warn loudly so the
    # operator notices.
    try:
        from PIL import Image, ImageOps  # type: ignore[import-not-found]

        img = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        w, h = img.size
        scale = _MAX_IMAGE_SIDE / max(w, h)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = BytesIO()
        # LOGIC: PNG round-trips lossless and preserves diagram crispness;
        # screenshots with smooth gradients would benefit from JPEG, but the
        # quality risk on UI-text legibility is not worth the savings for v1.
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    except ImportError:
        log.warning(
            "Pillow not installed — sending image at full resolution. "
            "Install requirements/base.txt to enable resize-and-cost-discipline."
        )
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f"data:{mime};base64,{b64}"


def vision_message(prompt: str, images: list[Path | str]) -> list[dict[str, Any]]:
    """Build the OpenAI ``messages`` payload for one user turn with N images.

    Returns a list with a SINGLE ``user`` message whose ``content`` is an
    interleaved list of ``{"type":"text",...}`` and ``{"type":"image_url",...}``
    parts. Text part first; image parts after. Some providers are order-
    sensitive to that convention.

    Example shape::

        [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
            ]}
        ]
    """
    parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img in images:
        url = (
            img
            if isinstance(img, str) and img.startswith("data:")
            else encode_image_to_data_url(img)
        )
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return [{"role": "user", "content": parts}]


class OpenRouterVision:
    """Real ``VisionLLM`` — composes ``OpenRouterClient`` with image plumbing."""

    def __init__(self, llm: OpenRouterClient | None = None) -> None:
        # NOTE: we accept an existing client so the cost cache stays warm
        # across vision and text calls in the same process.
        self.llm = llm or OpenRouterClient()

    @cached
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
            images: 1+ image paths or already-formatted data URIs.
            schema: Pydantic schema to enforce.
            model: Optional vision-capable model id; default from settings.

        Returns:
            A validated instance of ``schema``.

        Raises:
            ValueError: when ``images`` is empty.
            openai.OpenAIError: on transport / auth / rate-limit failures.
        """
        if not images:
            raise ValueError("OpenRouterVision.analyze requires at least one image")

        # LOGIC: encode + assemble. The shared ``_chat_with_schema`` worker on
        # OpenRouterClient handles retries, json_object fallback, and validation,
        # so this method stays a thin assembler.
        data_urls: list[Path | str] = [encode_image_to_data_url(img) for img in images]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            *vision_message(user, data_urls),
        ]
        return self.llm._chat_with_schema(
            messages=messages,
            schema=schema,
            model=model or settings.default_vision_model,
            # NOTE: vision tasks benefit from determinism — pin temperature
            # at the configured default (0.2). Override per-call only when
            # you have measured a need.
            temperature=settings.default_temperature,
        )
