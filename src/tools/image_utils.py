"""Pure image helpers — no LLM, no network.

OWNER: Person B (used by everyone)
SPRINT CONCEPTS: pre-processing for both RAG (Sprint 3) and multimodal LLM
    calls (Sprint 1). Cost-discipline (Sprint 5) lives here too.
CONSUMES: ``Pillow``.
PROVIDES: load_image, resize_max_side, to_data_url, side_by_side, thumbnail,
    annotate_box.

WHY YOU CARE
------------
Every agent that hands an image to the vision LLM should resize first.
Without it, a 4 K screenshot costs ~3× the tokens of a 1024 px one. With
five agents calling the LLM on the same image, that 3× compounds into 15×
over one click of "Run". Centralizing the resize here keeps the discipline
in one place.

DEFINITION OF DONE
------------------
[ ] ``load_image`` works on .png, .jpg, .jpeg, .webp; raises FileNotFoundError
    on missing path.
[ ] ``resize_max_side(img, 1024)`` preserves aspect ratio. A square 4096
    image returns 1024×1024; a 4096×2048 returns 1024×512.
[ ] ``to_data_url`` round-trips: ``encode → decode → ImageOps.compare`` is
    pixel-identical.
[ ] ``side_by_side([a, b, c])`` produces ONE image with a-b-c left to right
    sharing a common height.
[ ] ``thumbnail`` is fast (< 50 ms for a 4 K source) — it must be cheap
    enough to call inside the Gradio gallery render.

DO NOT
------
- Do not import opencv. We use Pillow only — opencv pulls a 50 MB wheel and
  duplicates capability. opencv is reserved for Person D's contrast pass.
- Do not return Pillow images from public APIs that cross modules. Convert
  to data-URI strings or numpy arrays at the boundary.
- Do not load the same image twice. If you call ``resize_max_side`` after
  ``load_image``, pass the Image object — don't re-open the path.
- Do not strip EXIF asymmetrically. If you call ``ImageOps.exif_transpose``
  in one code path, do it in *all* paths or scores drift between
  ingest-time and query-time.
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PIL import Image as _Image  # type: ignore[import-not-found]


def load_image(path: Path | str) -> "_Image.Image":
    """Open ``path`` and convert to RGB.

    Raises:
        FileNotFoundError: when the path does not exist.
    """
    # HINT: three lines:
    #   from PIL import Image, ImageOps
    #   img = Image.open(path)
    #   return ImageOps.exif_transpose(img).convert("RGB")
    #
    # NOTE: we always exif_transpose so phone screenshots come out upright.
    # CLIP and the vision LLM both score better on upright images.
    # TODO(person-b): implement.
    from PIL import Image, ImageOps

    img = Image.open(path)
    return ImageOps.exif_transpose(img).convert("RGB")


def resize_max_side(img: "_Image.Image", max_side: int = 1024) -> "_Image.Image":
    """Resize so the longest side is ``max_side`` px, preserving aspect ratio.

    Returns the input unchanged when it is already smaller than ``max_side``.
    """
    # HINT: ~5 lines:
    #   from PIL import Image
    #   w, h = img.size
    #   scale = max_side / max(w, h)
    #   if scale >= 1.0:
    #       return img            # already small enough
    #   return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    #
    # LOGIC: LANCZOS is the best quality/speed trade-off for downsampling.
    # NEAREST is wrong (jagged), BILINEAR is acceptable for thumbnails only.
    # TODO(person-b): implement.
    from PIL import Image

    w, h = img.size
    scale = max_side / max(w, h)
    if scale >= 1.0:
        return img
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def to_data_url(img: "_Image.Image", fmt: str = "PNG") -> str:
    """PIL Image → ``data:image/<fmt>;base64,...`` data URI.

    Used by ``llm.multimodal.encode_image_to_data_url`` and tests.
    """
    # HINT: four lines:
    #   buf = BytesIO()
    #   img.save(buf, format=fmt)
    #   b64 = base64.b64encode(buf.getvalue()).decode()
    #   return f"data:image/{fmt.lower()};base64,{b64}"
    #
    # NOTE: PNG is a safe default. Use JPEG only if you can tolerate
    # quality loss (you can for screenshots; you cannot for diagrams).
    # TODO(person-b): implement.
    buf = BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/{fmt.lower()};base64,{b64}"


def side_by_side(
    images: list["_Image.Image"],
    gap: int = 8,
    bg: tuple[int, int, int] = (255, 255, 255),
) -> "_Image.Image":
    """Composite N images horizontally with a gap.

    Used by the brand agent to send ONE composite (candidate + retrieved
    refs) to the vision LLM instead of N separate uploads. Cost discipline.
    """
    # HINT: six-step recipe:
    #   from PIL import Image
    #   if not images: raise ValueError("side_by_side: empty list")
    #   target_h = min(im.height for im in images)
    #   resized = [im.resize((int(im.width * target_h / im.height), target_h)) for im in images]
    #   total_w = sum(im.width for im in resized) + gap * (len(resized) - 1)
    #   canvas = Image.new("RGB", (total_w, target_h), bg)
    #   x = 0
    #   for im in resized:
    #       canvas.paste(im, (x, 0))
    #       x += im.width + gap
    #   return canvas
    #
    # NOTE: equal heights make the composite look like a comparison, not a
    # ransom note. If your refs are very different aspect ratios, consider
    # padding to a common height instead of resizing.
    # TODO(person-b): implement.
    from PIL import Image

    if not images:
        raise ValueError("side_by_side: empty list")
    target_h = min(im.height for im in images)
    resized = [
        im.resize((int(im.width * target_h / im.height), target_h)) for im in images
    ]
    total_w = sum(im.width for im in resized) + gap * (len(resized) - 1)
    canvas = Image.new("RGB", (total_w, target_h), bg)
    x = 0
    for im in resized:
        canvas.paste(im, (x, 0))
        x += im.width + gap
    return canvas


def annotate_box(img: "_Image.Image", box: tuple[int, int, int, int], label: str) -> "_Image.Image":
    """Draw a labeled rectangle on a copy of ``img``. Used by the report tab.

    Returns a NEW image — never mutate the input.
    """
    # HINT: six lines:
    #   from PIL import ImageDraw
    #   out = img.copy()
    #   draw = ImageDraw.Draw(out)
    #   draw.rectangle(box, outline=(255, 0, 0), width=3)
    #   draw.text((box[0], max(box[1] - 14, 0)), label, fill=(255, 0, 0))
    #   return out
    # TODO(person-b, post-MVP): implement once the UI uses it.
    from PIL import ImageDraw

    out = img.copy()
    draw = ImageDraw.Draw(out)
    draw.rectangle(box, outline=(255, 0, 0), width=3)
    draw.text((box[0], max(box[1] - 14, 0)), label, fill=(255, 0, 0))
    return out


def thumbnail(path: Path | str, size: tuple[int, int] = (256, 256)) -> "_Image.Image":
    """Cheap thumbnail for the Gradio gallery."""
    # HINT: three lines:
    #   img = load_image(path)
    #   img.thumbnail(size)   # in-place, preserves aspect ratio
    #   return img
    # TODO(person-b): implement.
    img = load_image(path)
    img.thumbnail(size)
    return img
