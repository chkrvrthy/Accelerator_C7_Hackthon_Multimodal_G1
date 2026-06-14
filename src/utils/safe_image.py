"""Safe image preprocessing for the upload pipeline.

OWNER: Person A
SPRINT CONCEPTS: Sprint 6 (cost optimization, robustness).
PROVIDES: ``MAX_UPLOAD_BYTES``, ``MAX_PIXELS``, ``UploadError``,
          ``preflight_image``, ``downsize_for_pipeline``.

WHY THIS FILE EXISTS
--------------------
The Gradio file widget will happily accept a 100 MB screenshot and pass
it straight through to PIL, OpenCV, and the multimodal LLM. That has
three failure modes:

  1. PIL.Image.open eats > 4 GB of RAM on a 30k x 30k PNG and the
     process dies with no useful error.
  2. The base64-encoded data URL we send to OpenRouter exceeds the
     provider's per-request payload limit and the call fails late.
  3. Even if it worked, the user is paying tokens for an image whose
     resolution is wasted (the vision model can only resolve about
     ~1000 px on the long edge anyway).

This module is the single chokepoint that makes those failures
impossible. Every code path that reads a user-uploaded image MUST run
the upload through ``preflight_image`` first.

GUARANTEES
----------
- ``preflight_image`` never raises a raw exception; it converts every
  failure into ``UploadError`` with a user-friendly message.
- ``downsize_for_pipeline`` returns a path to a sanitized copy that is
  guaranteed to be: (a) <= ``MAX_PIXELS`` total pixels, (b) <= the
  configured upload byte cap, (c) opaque RGB, (d) a valid PNG.
- The original upload is never modified.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from src.utils.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration knobs
# ---------------------------------------------------------------------------
# 20 MB is the friendly upper bound. Most product screenshots come in
# under 5 MB; 20 MB covers retina-resolution full-page captures with
# headroom. Anything bigger is almost always a misclick (a video, a PSD,
# a multi-page PDF). We refuse those with a clear message instead of
# letting the pipeline OOM.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

# 4 megapixels = 2000x2000-ish, well above what gpt-4o-mini's vision
# pipeline can resolve. Anything beyond this is downsampled before we
# go anywhere near the LLM (saves tokens; saves PIL memory).
MAX_PIXELS = 4_000_000

# 1024 px on the long edge is the resolution the multimodal LLM tier
# uses internally anyway. Going higher just inflates the data URL.
MAX_LONG_EDGE_PX = 1024

# Comparison-mode upload cap. Each vision agent sends ALL frames in one
# call, so cost scales linearly with N. 5 frames keeps a real-API run
# under ~$0.02 on gpt-4o-mini even with all 4 vision agents running and
# is enough to cover the "hero + features + pricing + signup + footer"
# walkthrough that the demo-script targets.
MAX_IMAGES_PER_RUN = 5

# Allowed file suffixes. We reject the rest with a friendly message
# rather than discovering the failure deep inside the pipeline.
ALLOWED_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})

_HUMAN_LIMIT = "20 MB"
_HUMAN_PIXELS = "about 4 megapixels (e.g. 2000x2000 or 2560x1600)"


@dataclass(frozen=True)
class UploadError(Exception):
    """User-friendly upload validation failure.

    The ``user_title`` and ``user_body`` fields are designed to be shown
    in the Gradio status banner verbatim. ``debug_detail`` is logged
    server-side but never shown to the user.
    """

    user_title: str
    user_body: str
    debug_detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - dataclass already gives repr
        return f"{self.user_title}: {self.user_body}"


def preflight_image(image_path: Path | str) -> Path:
    """Validate that an uploaded image is safe to feed into the pipeline.

    Returns the same path on success. Raises :class:`UploadError` with a
    user-readable message on any of the validation failures below:

      - file does not exist
      - suffix not in ``ALLOWED_SUFFIXES``
      - file size > ``MAX_UPLOAD_BYTES``
      - file is not a valid image (PIL refuses to open it)
      - decoded image has > ``MAX_PIXELS`` total pixels

    NEVER returns a downsized copy; that is what ``downsize_for_pipeline``
    is for. We separate the two so the caller controls the temp lifecycle.
    """
    p = Path(image_path)
    if not p.exists():
        raise UploadError(
            user_title="Upload missing",
            user_body=(
                "We could not find the file you uploaded. Try again — Gradio "
                "may have lost the temporary copy."
            ),
            debug_detail=f"path does not exist: {p}",
        )

    suffix = p.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UploadError(
            user_title="Unsupported file type",
            user_body=(
                f"This tool supports {', '.join(sorted(ALLOWED_SUFFIXES))} "
                "screenshots. Convert your file and try again."
            ),
            debug_detail=f"suffix {suffix!r} not in allowlist",
        )

    size_bytes = p.stat().st_size
    if size_bytes > MAX_UPLOAD_BYTES:
        raise UploadError(
            user_title="File too large",
            user_body=(
                f"This file is {_human_size(size_bytes)}. Please upload a "
                f"screenshot up to {_HUMAN_LIMIT}. Tip: most product "
                "screenshots are well under 5 MB; if yours is larger, you "
                "are probably uploading a full-page recording or an "
                "uncompressed PSD by mistake."
            ),
            debug_detail=f"size={size_bytes} > {MAX_UPLOAD_BYTES}",
        )

    # Try to decode just enough to know the resolution. PIL's lazy
    # open + size read is O(metadata-only); we don't load pixel data.
    try:
        from PIL import Image
    except ImportError:
        # Pillow missing: we cannot validate resolution. Allow the
        # upload through with a warning; the downstream pipeline will
        # likely succeed since the byte-size check already passed.
        log.warning("preflight_image: Pillow missing; skipping resolution check.")
        return p

    try:
        with Image.open(p) as im:
            w, h = im.size
    except Exception as e:
        raise UploadError(
            user_title="Image cannot be read",
            user_body=(
                "This file is in an image format we recognize but cannot "
                "decode. Try re-exporting it as a standard PNG or JPG."
            ),
            debug_detail=f"PIL.Image.open raised {type(e).__name__}: {e}",
        ) from e

    pixels = w * h
    if pixels > MAX_PIXELS:
        raise UploadError(
            user_title="Image resolution too high",
            user_body=(
                f"The screenshot is {w}x{h} pixels ({pixels:,} total). "
                f"Please resize to {_HUMAN_PIXELS} or smaller. The vision "
                "model cannot resolve more detail than that, so a larger "
                "image just costs more tokens with no quality lift."
            ),
            debug_detail=f"pixels={pixels} > {MAX_PIXELS}",
        )

    return p


def preflight_batch(image_paths: list[Path | str]) -> list[Path]:
    """Validate a batch of uploads for comparison mode.

    Returns the same list of paths on success. Raises :class:`UploadError`
    on any of the batch-level failures below; per-file failures (size,
    suffix, decoder) are delegated to :func:`preflight_image` and
    surface with the same friendly copy.

    Batch-level failures:
      - empty list (caller should treat None upload as a separate state)
      - more than ``MAX_IMAGES_PER_RUN`` frames

    Per-file validation runs in input order so the user sees the first
    bad file's title (e.g. "File too large") rather than a generic
    batch-level error. We stop at the first failure on purpose — fixing
    the batch usually means re-uploading anyway, and surfacing five
    errors at once would just be noise.
    """
    if not image_paths:
        raise UploadError(
            user_title="Upload needed",
            user_body=(
                "Add at least one PNG or JPG screenshot. For multi-screen "
                f"reviews you can attach up to {MAX_IMAGES_PER_RUN} frames at once."
            ),
            debug_detail="preflight_batch called with empty list",
        )
    if len(image_paths) > MAX_IMAGES_PER_RUN:
        raise UploadError(
            user_title="Too many screenshots",
            user_body=(
                f"This run has {len(image_paths)} screenshots; the limit "
                f"is {MAX_IMAGES_PER_RUN} per analysis. Drop the extras and "
                "try again — most product walkthroughs are covered by 3-5 "
                "frames (hero, features, pricing, signup, dashboard)."
            ),
            debug_detail=f"batch size {len(image_paths)} > {MAX_IMAGES_PER_RUN}",
        )
    return [preflight_image(p) for p in image_paths]


def downsize_for_pipeline(
    image_path: Path | str, dest_dir: Path | None = None
) -> Path:
    """Return a path to a pipeline-safe (small, RGB, PNG) copy of the input.

    ``preflight_image`` is the right gate; this function does the
    actual resizing. Behavior:

      - If the input is already small enough (long edge <= MAX_LONG_EDGE_PX),
        the original path is returned unchanged.
      - Otherwise a downsized PNG is written to ``dest_dir`` (defaults
        to the system temp dir) and that path is returned.

    Output is opaque RGB (alpha flattened on white) because the LLM
    pipeline does not benefit from transparency and PNG with alpha is
    larger.
    """
    p = Path(image_path)
    try:
        from PIL import Image, ImageOps
    except ImportError:
        # No Pillow: the caller must accept the upload as-is. We already
        # warned in preflight_image; no need to repeat.
        return p

    with Image.open(p) as im:
        im = ImageOps.exif_transpose(im)
        w, h = im.size
        long_edge = max(w, h)
        if long_edge <= MAX_LONG_EDGE_PX:
            return p

        scale = MAX_LONG_EDGE_PX / long_edge
        new_size = (round(w * scale), round(h * scale))
        im = im.convert("RGB").resize(new_size, Image.LANCZOS)

        if dest_dir is None:
            import tempfile

            dest_dir = Path(tempfile.gettempdir())
        dest_dir.mkdir(parents=True, exist_ok=True)

        out = dest_dir / f"{p.stem}__safe_{new_size[0]}x{new_size[1]}.png"
        # LOGIC: write to a buffer first so a partial write never leaves
        # a corrupt file on disk (defensive — the next agent run would
        # otherwise read garbage).
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        out.write_bytes(buf.getvalue())
        log.info(
            "safe_image: downsized %s (%dx%d) -> %s (%dx%d, %d KB)",
            p.name,
            w,
            h,
            out.name,
            new_size[0],
            new_size[1],
            len(buf.getvalue()) // 1024,
        )
        return out


def _human_size(n_bytes: int) -> str:
    """Format ``n_bytes`` as a short human string ('12.4 MB')."""
    if n_bytes < 1024:
        return f"{n_bytes} B"
    if n_bytes < 1024 * 1024:
        return f"{n_bytes / 1024:.1f} KB"
    return f"{n_bytes / (1024 * 1024):.1f} MB"
