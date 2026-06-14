"""Tests for the upload-safety preflight + downsize helpers.

These tests pin the contract that protects the LLM pipeline from
hostile / oversized / mis-typed uploads. The contract:

  - ``preflight_image`` raises :class:`UploadError` (NOT a generic
    ``Exception``) on every failure mode, with a user-readable title
    and body.
  - It accepts every well-formed image inside the size and resolution
    envelopes.
  - ``downsize_for_pipeline`` is a no-op for already-small images,
    returns the *original* path, never a copy.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.fakes.fixtures import ensure_sample_design
from src.utils.safe_image import (
    MAX_UPLOAD_BYTES,
    UploadError,
    downsize_for_pipeline,
    preflight_image,
)


def test_preflight_passes_a_clean_sample() -> None:
    out = preflight_image(ensure_sample_design())
    assert isinstance(out, Path)


def test_preflight_rejects_missing_file() -> None:
    with pytest.raises(UploadError) as ei:
        preflight_image("/tmp/does-not-exist-please.png")
    assert "Upload missing" in ei.value.user_title


def test_preflight_rejects_unsupported_suffix() -> None:
    f = Path(tempfile.mkstemp(suffix=".pdf")[1])
    f.write_bytes(b"%PDF-1.4 not actually a pdf")
    with pytest.raises(UploadError) as ei:
        preflight_image(f)
    assert "Unsupported" in ei.value.user_title
    assert ".pdf" not in ei.value.user_body  # never echo the bad suffix back


def test_preflight_rejects_oversized_file() -> None:
    f = Path(tempfile.mkstemp(suffix=".png")[1])
    # Header bytes so the file is at least syntactically a PNG; the size
    # check fires before PIL ever decodes pixels, so any blob works.
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"X" * (MAX_UPLOAD_BYTES + 1024))
    with pytest.raises(UploadError) as ei:
        preflight_image(f)
    assert "too large" in ei.value.user_title.lower()
    # The body must include the human-friendly size and the limit.
    body = ei.value.user_body
    assert "MB" in body
    assert "20 MB" in body


def test_downsize_returns_original_for_small_image() -> None:
    src = ensure_sample_design()
    out = downsize_for_pipeline(src)
    assert out == src, "small images must NOT be copied"


def test_upload_error_is_an_exception() -> None:
    e = UploadError(user_title="t", user_body="b")
    assert isinstance(e, Exception)
    # __str__ joins title + body for log readability
    assert "t" in str(e) and "b" in str(e)
