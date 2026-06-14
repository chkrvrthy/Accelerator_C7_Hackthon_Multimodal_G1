"""Cost-optimization layer — disk-backed JSON cache + tiered model selector.

OWNER: Person A
SPRINT CONCEPTS:
    - Sprint 5: Cost optimization. The cache is the demo win. Tier selection
      is documented as an extension point.
CONSUMES: ``src.config.settings``.
PROVIDES: ``prompt_hash``, ``ResponseCache``, ``select_model``, ``cached``.

WHY YOU CARE
------------
For a hackathon, the cache IS the entire cost story. A 5-second LLM call is
sub-millisecond on the second run. Re-running the demo screenshot is free,
so we can iterate fearlessly. Wire the decorator BEFORE you build the demo
data — first-time demo writers always forget this and burn $20.

LOGIC OUTLINE
-------------
1. ``prompt_hash`` builds a stable SHA-256 over a canonical JSON of inputs.
   Same prompt → same hash → cache hit.
2. ``ResponseCache`` reads/writes ``data/cache/<hash>.json``.
3. ``cached`` is a decorator that wraps ``LLMClient.complete`` /
   ``VisionLLM.analyze`` with read-through-cache semantics.
4. ``select_model`` is a one-liner stub for the tiered model selector.

DEFINITION OF DONE
------------------
[ ] ``prompt_hash`` is identical for the same args in any order
    (``sort_keys=True`` already does this — verify in tests).
[ ] ``ResponseCache.get`` returns ``None`` on miss, dict on hit. Never raises
    on a corrupt cache file — log warning, return None.
[ ] ``ResponseCache.put`` writes atomically (temp file + rename) so a crash
    mid-write never leaves a half-file the next run will read.
[ ] ``CACHE_DISABLED=1`` round-trips: cache reads no-op, but writes still
    happen so subsequent runs benefit. (Or skip writes too — document choice.)
[ ] Decorator preserves the wrapped function's signature for IDEs.

DO NOT
------
- Do not key by image path. Two designers with different filenames for the
  same bytes should hit the same cache. Hash bytes in a separate field.
- Do not cache exceptions. A 500 error today is not a 500 error tomorrow.
- Do not put non-serializable values into the cache (numpy arrays, Paths).
  Convert to lists / strings first.
- Do not log full prompts at INFO. The hash is enough; full prompts go to
  LangSmith if anyone needs to inspect them.

KEY-DESIGN
----------
Cache key includes the *schema name* — different schemas produce different
JSON, so identical text+image with different schema is a legitimate miss.
Image inputs are hashed by *content*, not by path, so renaming files does
not invalidate the cache.
"""
from __future__ import annotations

import hashlib
import json
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from src.utils.logger import get_logger

log = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., BaseModel])


def _cfg() -> Any:
    """Re-read ``settings`` lazily so ``tmp_settings`` monkeypatch wins in tests."""
    from src import config as _c
    return _c.settings


def _hash_image_input(img: Any) -> str:
    """Stable content hash for any image input the vision LLM can consume.

    Files → sha256 of bytes. Data-URIs → sha256 of the URI string. PIL.Image
    or anything else → sha256 of repr (best-effort, won't be content-stable
    across processes but is at least intra-call deterministic).
    """
    if isinstance(img, (str, Path)):
        s = str(img)
        if s.startswith("data:"):
            return hashlib.sha256(s.encode()).hexdigest()
        p = Path(s)
        if p.exists():
            return hashlib.sha256(p.read_bytes()).hexdigest()
        return hashlib.sha256(s.encode()).hexdigest()
    return hashlib.sha256(repr(img).encode()).hexdigest()


def prompt_hash(
    *,
    system: str,
    user: str,
    images: list[str],
    schema_name: str,
    model: str,
) -> str:
    """Stable SHA-256 over a canonical JSON of all cache-relevant inputs.

    Returns a 64-char hex digest suitable for use as a filename.
    """
    # LOGIC: ``sort_keys=True`` makes the JSON canonical regardless of dict
    # insertion order. ``ensure_ascii=False`` keeps non-ASCII glyphs (e.g.
    # the user's ``₹`` in instructions) byte-stable.
    #
    # HINT: when an image is passed as a path or PIL.Image, hash its bytes
    # in your caller and pass the hex digest in ``images=[bytes_sha256]``.
    # NEVER pass a Path here — it would change the key when files move.
    payload = {"system": system, "user": user, "images": images, "schema": schema_name, "model": model}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


class ResponseCache:
    """Disk-backed JSON cache. One file per key under ``cache_dir``.

    Cache reads honour ``settings.cache_disabled`` (always miss when disabled).
    Cache writes always happen — so a "disabled" demo run still warms the
    cache for the next non-disabled run.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.dir = Path(cache_dir) if cache_dir is not None else Path(_cfg().cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        """Return cached dict or ``None`` on miss / IO error.

        Never raises — a corrupt cache must not break the demo.
        """
        if _cfg().cache_disabled:
            return None
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            # LOGIC: corrupt cache files happen (Ctrl-C mid-write before we had
            # the temp+rename pattern). Warn loudly so operators notice, but
            # never escalate to an exception that breaks the run.
            log.warning("cache.get corrupt or unreadable %s: %s", p.name, e)
            return None

    def put(self, key: str, value: dict[str, Any]) -> None:
        """Atomically write the cache entry (temp file + rename)."""
        p = self._path(key)
        tmp = p.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            # LOGIC: POSIX rename is atomic; on Windows, Path.replace also
            # provides atomic-replace semantics on the same volume.
            tmp.replace(p)
        except OSError as e:
            # LOGIC: a write failure (full disk, permission denied, NFS hiccup)
            # must NOT crash the user's analysis run. The cache is best-effort.
            log.warning("cache.put failed for %s: %s", p.name, e)


def select_model(task: str = "default") -> str:
    """Return a model id appropriate for ``task``.

    LOGIC: deliberately a one-liner stub — see plan.md "Demoted to thin stub".
    Extensions documented as "post-MVP" in `docs/PERSON_A_infra.md`.
    """
    cfg = _cfg()
    if task == "vision":
        return cfg.default_vision_model
    return cfg.default_text_model


def cached(fn: F) -> F:
    """Decorator: hash inputs, return cached result on hit, call through on miss.

    Wrap ``LLMClient.complete`` and ``VisionLLM.analyze`` with this in their
    real implementations. The fakes intentionally bypass the cache.

    Example::

        class OpenRouterClient:
            @cached
            def complete(self, *, system, user, schema, model=None, ...):
                ...

    Cache contract:
      * Same (system, user, image-bytes-hash, schema, model) → cache hit.
      * Different schema with same prompt → legitimate miss (different output).
      * Image input is hashed by **content**, not by path, so file renames
        do not invalidate the cache.
      * Exceptions are NEVER cached (a transient 500 today is not 500 tomorrow).
    """
    @wraps(fn)
    def _wrapped(self: Any, **kwargs: Any) -> BaseModel:
        cfg = _cfg()
        schema: type[BaseModel] = kwargs["schema"]
        # LOGIC: ``model`` may be None — pick the right default by call shape.
        # Vision calls pass ``images``; text calls don't.
        is_vision = bool(kwargs.get("images"))
        model = kwargs.get("model") or (
            cfg.default_vision_model if is_vision else cfg.default_text_model
        )
        image_hashes = [_hash_image_input(img) for img in (kwargs.get("images") or [])]
        key = prompt_hash(
            system=kwargs.get("system", ""),
            user=kwargs.get("user", ""),
            images=image_hashes,
            schema_name=schema.__name__,
            model=model,
        )

        cache = ResponseCache()
        hit = cache.get(key)
        if hit is not None:
            try:
                result = schema.model_validate(hit)
                log.debug("cache.hit %s.%s key=%s", fn.__qualname__, schema.__name__, key[:8])
                return result
            except Exception as e:  # noqa: BLE001 — corrupt entry, fall through.
                log.warning("cache.hit but %s validation failed (%s); refetching",
                            schema.__name__, e)

        log.debug("cache.miss %s.%s key=%s", fn.__qualname__, schema.__name__, key[:8])
        result = fn(self, **kwargs)
        try:
            cache.put(key, result.model_dump())
        except Exception as e:  # noqa: BLE001 — never let cache write break the run.
            log.warning("cache.put unexpected error: %s", e)
        return result

    return _wrapped  # type: ignore[return-value]
