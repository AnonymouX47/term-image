"""KittyImage-specific tests"""

import io
from base64 import standard_b64decode
from operator import mul
from random import random
from zlib import decompress

import pytest

from term_image.image.common import _ALPHA_THRESHOLD
from term_image.image.kitty import _END, _START, LINES, WHOLE, KittyImage

from .common import *  # noqa:F401
from .common import _size, python_img, setup_common

for name in tuple(globals()):
    if name.endswith("_Text"):
        del globals()[name]


@pytest.mark.order("first")
def test_setup_common():
    setup_common(KittyImage)


def test_set_render_method():
    try:
        assert KittyImage._render_method == KittyImage._default_render_method == LINES
        image = KittyImage(python_img)
        assert image._render_method == KittyImage._default_render_method

        assert KittyImage.set_render_method(WHOLE) is True
        assert KittyImage._render_method == WHOLE
        assert image._render_method == WHOLE

        assert image.set_render_method(LINES) is True
        assert image._render_method == LINES

        assert image.set_render_method() is True
        assert image._render_method == WHOLE

        assert KittyImage.set_render_method(LINES) is True
        assert KittyImage._render_method == LINES
        assert image._render_method == LINES

        assert image.set_render_method(WHOLE) is True
        assert image._render_method == WHOLE

        assert image.set_render_method() is True
        assert image._render_method == LINES

        assert KittyImage.set_render_method(WHOLE) is True
        assert KittyImage._render_method == WHOLE
        assert image._render_method == WHOLE

        assert KittyImage.set_render_method() is True
        assert KittyImage._render_method == KittyImage._default_render_method
        assert image._render_method == KittyImage._default_render_method
    finally:
        KittyImage._render_method = KittyImage._default_render_method


def expand_control_data(control_data):
    control_data = control_data.split(",")
    control_codes = {tuple(code.split("=")) for code in control_data}
    assert len(control_codes) == len(control_data)

    return control_codes


def decode_image(data):
    transmission, end, spaces = data.rpartition(_END)
    assert end == _END

    control_data, chunked_payload = transmission.split(";", 1)
    control_codes = expand_control_data(control_data)
    assert (
        code in control_codes for code in expand_control_data("a=T,t=d,z=0,o=z,C=1")
    )

    with io.StringIO() as full_payload:
        # Implies every split after the first would've started with _START
        chunks = chunked_payload.split(_START)
        first_chunk = chunks.pop(0)

        if chunks:
            last_chunk = chunks.pop()
            payload, end, empty = first_chunk.partition(_END)
            assert end == _END
            assert empty == ""
            assert ("m", "1") in control_codes
        else:
            last_chunk = ""
            payload = first_chunk
            assert ("m", "0") in control_codes

        assert len(payload) <= 4096
        assert payload.isprintable() and " " not in payload
        full_payload.write(payload)

        for chunk in chunks:
            transmission, end, empty = chunk.partition(_END)
            assert end == _END
            assert empty == ""
            control_data, payload = transmission.split(";")
            assert ("m", "1") in expand_control_data(control_data)
            assert len(payload) <= 4096
            assert payload.isprintable() and " " not in payload
            full_payload.write(payload)

        if last_chunk:
            # _END was removed at the beginning
            control_data, payload = last_chunk.split(";")
            assert ("m", "0") in expand_control_data(control_data)
            assert len(payload) <= 4096
            assert payload.isprintable() and " " not in payload
            full_payload.write(payload)

        raw_image = decompress(standard_b64decode(full_payload.getvalue().encode()))

    return control_codes, raw_image, spaces


def get_actual_render_size(image):
    render_size = image._get_render_size()
    _, r_height = image.rendered_size
    width, height = (
        render_size
        if mul(*render_size) < mul(*image._original_size)
        else image._original_size
    )
    extra = height % (r_height or 1)
    if extra:
        height = height - extra + r_height

    return width, height


def test_minimal_render_size():
    image = KittyImage.from_file("tests/images/trans.png")
    lines_for_original_height = KittyImage._pixels_lines(pixels=image.original_size[1])

    # Using render size
    image.height = lines_for_original_height // 2
    w, h = image._get_render_size()
    lines = image.height
    bytes_per_line = w * (h // lines) * 4

    assert get_actual_render_size(image) == (w, h)
    for line in str(image).splitlines():
        control_codes, raw_image, _ = decode_image(line[len(_START) :])
        assert (
            code in control_codes
            for code in expand_control_data(f"s={w},v={h // lines}")
        )
        assert len(raw_image) == bytes_per_line

    # Using original size
    image.height = lines_for_original_height * 2
    w, h = image._original_size
    lines = image.height
    extra = h % (lines or 1)
    if extra:
        h = h - extra + lines
    bytes_per_line = w * (h // lines) * 4

    assert get_actual_render_size(image) == (w, h)
    for line in str(image).splitlines():
        control_codes, raw_image, _ = decode_image(line[len(_START) :])
        assert (
            code in control_codes
            for code in expand_control_data(f"s={w},v={h // lines}")
        )
        assert len(raw_image) == bytes_per_line
