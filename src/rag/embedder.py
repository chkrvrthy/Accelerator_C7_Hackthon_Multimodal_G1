"""CLIP embedder — image and text into the SAME vector space.

OWNER: Person B
SPRINT CONCEPTS:
    - Sprint 3: Embeddings (the "E" in RAG).
CONSUMES: ``open_clip_torch``, ``torch``, ``Pillow``.
PROVIDES: ``CLIPEmbedder`` with ``embed_image``, ``embed_text``, ``embed_batch``.

WHY YOU CARE
------------
Because CLIP's text encoder and image encoder share an output space, you can
search images using a text query — and vice versa. That single property is
what lets the UI's "browse references" tab do "fintech dashboard" → top-5
PNGs without OCR or captioning. Image RAG lives or dies on this file.

LOGIC OUTLINE
-------------
1. On first use, load the CLIP checkpoint (~600 MB on disk for ViT-B-32).
2. ``embed_image`` resizes/normalizes the image, runs the visual encoder,
   L2-normalizes the resulting vector.
3. ``embed_text`` tokenizes the query, runs the text encoder, L2-normalizes.
4. Both methods return ``np.ndarray`` of dtype float32 with the same dim.

DEFINITION OF DONE
------------------
[ ] Construction is idempotent — calling ``CLIPEmbedder()`` ten times
    loads the model once (class-level cache).
[ ] ``embed_image`` and ``embed_text`` return shape ``(512,)`` for ViT-B-32.
[ ] Both vectors are L2-normalized: ``abs(np.linalg.norm(v) - 1.0) < 1e-3``.
[ ] CPU works without CUDA installed.
[ ] ``embed_batch([img1, img2, ...])`` returns ``(N, 512)``.
[ ] tests/person_b/test_embedder.py passes when torch+open_clip installed.

DO NOT
------
- Do not call ``model.eval()`` in your code — open_clip's
  ``create_model_and_transforms`` returns a model already in eval mode.
- Do not skip ``F.normalize``. LanceDB's cosine metric assumes unit vectors;
  unnormalized vectors silently rank wrong.
- Do not allocate a new model per ``CLIPEmbedder()`` instance. Use the
  class-level ``_shared`` cache.
- Do not block the GIL with a giant batch. Person B's batch_size = 8 is
  the right default; bigger only if you measured.

PITFALLS
--------
- EXIF rotation: Pillow auto-rotates based on EXIF; CLIP expects the image
  the way it was saved. Strip EXIF or apply ``ImageOps.exif_transpose`` once
  and stick with it across ingest and query — otherwise scores drift.
- ``open_clip_torch`` ships many checkpoints; default
  ``ViT-B-32 / laion2b_s34b_b79k`` is small and CPU-runnable.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from src.config import settings
from src.utils.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np
    from PIL import Image

log = get_logger(__name__)


class CLIPEmbedder:
    """One model, two methods. Image and text in the same 512-d space."""

    # LOGIC: class-level cache keyed by (model_name, pretrained) so re-creating
    # the embedder is free. Multi-process workers share through OS file cache,
    # not memory — ingest CLI is single-process so it's fine.
    _shared: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        model_name: str = settings.clip_model,
        pretrained: str = settings.clip_pretrained,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.pretrained = pretrained
        self.device = device  # set inside the load helper below
        self.dim: int = 512  # ViT-B-32 = 512; ViT-L/14 = 768 — update if you swap.
        # HINT: do NOT load the model here. The first method call triggers
        # the load via _ensure_loaded(). This keeps `import` cheap so other
        # slices that just type-check this file pay nothing.

    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> tuple[Any, Any, Any]:
        """Return (model, preprocess, tokenizer), loading once per class."""
        # HINT: full recipe (~10 lines):
        #   import torch, open_clip
        #   key = f"{self.model_name}::{self.pretrained}"
        #   if key in self._shared: return self._shared[key]
        #   self.device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        #   model, _, preprocess = open_clip.create_model_and_transforms(
        #       self.model_name, pretrained=self.pretrained, device=self.device,
        #   )
        #   tokenizer = open_clip.get_tokenizer(self.model_name)
        #   self._shared[key] = (model, preprocess, tokenizer)
        #   return self._shared[key]
        # TODO(person-b): implement.
        import open_clip
        import torch

        key = f"{self.model_name}::{self.pretrained}"
        if key in self._shared:
            cached = self._shared[key]
            self.device = cached[3]
            return cached[:3]

        self.device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        model, _, preprocess = open_clip.create_model_and_transforms(
            self.model_name,
            pretrained=self.pretrained,
            device=self.device,
        )
        tokenizer = open_clip.get_tokenizer(self.model_name)
        self._shared[key] = (model, preprocess, tokenizer, self.device)
        return self._shared[key][:3]

    # ------------------------------------------------------------------
    def embed_image(self, image: Path | str | Image.Image) -> np.ndarray:
        """Return an L2-normalized 512-d float32 vector for one image."""
        # HINT: five-step recipe:
        #   1. model, preprocess, _ = self._ensure_loaded()
        #   2. if isinstance(image, (str, Path)):
        #         from PIL import Image, ImageOps
        #         img = ImageOps.exif_transpose(Image.open(image)).convert("RGB")
        #      else:
        #         img = image.convert("RGB")
        #   3. tensor = preprocess(img).unsqueeze(0).to(self.device)
        #   4. with torch.no_grad():
        #          emb = model.encode_image(tensor)
        #          emb = torch.nn.functional.normalize(emb, dim=-1)
        #   5. return emb.squeeze(0).cpu().numpy().astype("float32")
        #
        # HINT: when device is CPU and image count > 50, log a warning so
        # the demo author knows to run with GPU for the ingest step.
        # TODO(person-b): implement.
        import torch

        from src.tools.image_utils import load_image

        model, preprocess, _ = self._ensure_loaded()
        img = load_image(image) if isinstance(image, (str, Path)) else image.convert("RGB")
        tensor = preprocess(img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            emb = model.encode_image(tensor)
            emb = torch.nn.functional.normalize(emb, dim=-1)
        return emb.squeeze(0).cpu().numpy().astype("float32")

    def embed_text(self, text: str) -> np.ndarray:
        """Return an L2-normalized 512-d float32 vector for one query."""
        # HINT: four-step recipe:
        #   1. model, _, tokenizer = self._ensure_loaded()
        #   2. tokens = tokenizer([text]).to(self.device)
        #   3. with torch.no_grad():
        #          emb = model.encode_text(tokens)
        #          emb = torch.nn.functional.normalize(emb, dim=-1)
        #   4. return emb.squeeze(0).cpu().numpy().astype("float32")
        # TODO(person-b): implement.
        import torch

        model, _, tokenizer = self._ensure_loaded()
        tokens = tokenizer([text]).to(self.device)
        with torch.no_grad():
            emb = model.encode_text(tokens)
            emb = torch.nn.functional.normalize(emb, dim=-1)
        return emb.squeeze(0).cpu().numpy().astype("float32")

    def embed_batch(self, images: list[Path | str]) -> np.ndarray:
        """Optional bulk path used by the ingest CLI.

        Returns shape ``(N, dim)``.
        """
        # HINT: simplest correct version (no DataLoader, no async):
        #   import torch, numpy as np
        #   model, preprocess, _ = self._ensure_loaded()
        #   batch = torch.stack([preprocess(_load_rgb(p)) for p in images]).to(self.device)
        #   with torch.no_grad():
        #       embs = model.encode_image(batch)
        #       embs = torch.nn.functional.normalize(embs, dim=-1)
        #   return embs.cpu().numpy().astype("float32")
        #
        # NOTE: for >256 images, chunk into batches of 64 to keep memory
        # bounded. Premature optimization until then.
        # TODO(person-b): implement.
        import numpy as np
        import torch

        from src.tools.image_utils import load_image

        if not images:
            return np.empty((0, self.dim), dtype="float32")

        model, preprocess, _ = self._ensure_loaded()
        if self.device == "cpu" and len(images) > 50:
            log.warning("embedding %d images on CPU; ingest will be faster with CUDA", len(images))
        chunks: list[np.ndarray] = []
        for start in range(0, len(images), 64):
            batch_paths = images[start : start + 64]
            batch = torch.stack([preprocess(load_image(p)) for p in batch_paths]).to(self.device)
            with torch.no_grad():
                embs = model.encode_image(batch)
                embs = torch.nn.functional.normalize(embs, dim=-1)
            chunks.append(embs.cpu().numpy().astype("float32"))
        return np.vstack(chunks)
