"""Bundled fixtures used by every fake and every test.

OWNER: Person A

We bundle ONE tiny PNG so a fresh clone can run end-to-end without anyone
copying images around. Keep this file small (<10 KB) and committed to git.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_DESIGN: Path = FIXTURES_DIR / "sample.png"


def _build_minimal_png(path: Path) -> None:
    """Write a 16x16 solid-blue PNG to ``path`` using only stdlib.

    LOGIC: Pillow is not always installed in every slice, but the fakes
    package promises "no third-party imports". We hand-roll a minimal valid
    PNG with stdlib so even a CI matrix without Pillow can run the tests.
    """
    width = height = 16
    # filter byte (0) per scanline + 4 bytes RGBA per pixel.
    raw = b""
    for _ in range(height):
        raw += b"\x00" + (b"\x0a\x25\x40\xff" * width)  # navy fill

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(raw))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def ensure_sample_design() -> Path:
    """Idempotent helper — return the bundled sample, creating it if missing.

    Tests and per-slice ``__main__`` runners call this so the file is
    guaranteed to exist whether or not the user ran ``git lfs`` or similar.
    """
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    if not SAMPLE_DESIGN.exists():
        _build_minimal_png(SAMPLE_DESIGN)
    return SAMPLE_DESIGN
