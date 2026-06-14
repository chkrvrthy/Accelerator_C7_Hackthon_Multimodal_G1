"""Person B image utility coverage."""

from __future__ import annotations

import base64
from io import BytesIO

import pytest

pytestmark = pytest.mark.person_b


def test_load_image_and_resize_preserves_aspect(tiny_png):
    from src.tools.image_utils import load_image, resize_max_side

    img = load_image(tiny_png)
    assert img.mode == "RGB"
    assert img.size == (32, 32)

    resized = resize_max_side(img.resize((100, 50)), max_side=25)
    assert resized.size == (25, 12)


def test_to_data_url_round_trips(tiny_png):
    from PIL import Image

    from src.tools.image_utils import load_image, to_data_url

    img = load_image(tiny_png)
    prefix, b64 = to_data_url(img).split(",", 1)
    assert prefix == "data:image/png;base64"
    decoded = Image.open(BytesIO(base64.b64decode(b64))).convert("RGB")
    assert decoded.size == img.size


def test_side_by_side_and_thumbnail(tiny_png):
    from src.tools.image_utils import load_image, side_by_side, thumbnail

    a = load_image(tiny_png).resize((40, 20))
    b = load_image(tiny_png).resize((20, 20))
    combined = side_by_side([a, b], gap=4)
    assert combined.size == (64, 20)

    thumb = thumbnail(tiny_png, size=(16, 16))
    assert max(thumb.size) == 16


def test_side_by_side_rejects_empty_list():
    from src.tools.image_utils import side_by_side

    with pytest.raises(ValueError):
        side_by_side([])
