"""ITerm2Image-specific tests"""

import pytest

from term_image.exceptions import ITerm2ImageError
from term_image.image.iterm2 import LINES, WHOLE, ITerm2Image

from . import common
from .common import python_img, setup_common

for name, obj in vars(common).items():
    if name.endswith(("_All", "_Graphics")):
        globals()[name] = obj


@pytest.mark.order("first")
def test_setup_common():
    setup_common(ITerm2Image)


def test_set_render_method():
    try:
        assert ITerm2Image._render_method == ITerm2Image._default_render_method == LINES
        image = ITerm2Image(python_img)
        assert image._render_method == ITerm2Image._default_render_method

        # Case-insensitivity
        assert ITerm2Image.set_render_method(WHOLE.upper()) is None
        assert ITerm2Image.set_render_method(WHOLE.lower()) is None
        assert ITerm2Image.set_render_method(LINES.upper()) is None
        assert ITerm2Image.set_render_method(LINES.lower()) is None

        assert ITerm2Image.set_render_method(WHOLE) is None
        assert ITerm2Image._render_method == WHOLE
        assert image._render_method == WHOLE

        assert image.set_render_method(LINES) is None
        assert image._render_method == LINES

        assert image.set_render_method() is None
        assert image._render_method == WHOLE

        assert ITerm2Image.set_render_method(LINES) is None
        assert ITerm2Image._render_method == LINES
        assert image._render_method == LINES

        assert image.set_render_method(WHOLE) is None
        assert image._render_method == WHOLE

        assert image.set_render_method() is None
        assert image._render_method == LINES

        assert ITerm2Image.set_render_method(WHOLE) is None
        assert ITerm2Image._render_method == WHOLE
        assert image._render_method == WHOLE

        assert ITerm2Image.set_render_method() is None
        assert ITerm2Image._render_method == ITerm2Image._default_render_method
        assert image._render_method == ITerm2Image._default_render_method
    finally:
        ITerm2Image._render_method = ITerm2Image._default_render_method


def test_style_format_spec():
    for spec in (
        " ",
        "x",
        "LW",
        "WN",
        "c1m0",
        "0c",
        "m2",
        "m01",
        "c-1",
        "c10",
        "c4m1",
        " c1",
        "m0 ",
        "  m1c3  ",
    ):
        with pytest.raises(ITerm2ImageError, match="format spec"):
            ITerm2Image._check_style_format_spec(spec, spec)

    for spec, args in (
        ("", {}),
        ("L", {"method": LINES}),
        ("W", {"method": WHOLE}),
        ("N", {"native": True}),
        ("m0", {}),
        ("m1", {"mix": True}),
        ("c4", {}),
        ("c0", {"compress": 0}),
        ("c9", {"compress": 9}),
        ("Wm1c9", {"method": WHOLE, "mix": True, "compress": 9}),
    ):
        assert ITerm2Image._check_style_format_spec(spec, spec) == args


class TestStyleArgs:
    def test_unknown(self):
        for args in ({"c": 1}, {"m": True}, {" ": None}, {"xxxx": True}):
            with pytest.raises(ITerm2ImageError, match="Unknown style-specific"):
                ITerm2Image._check_style_args(args)

    def test_method(self):
        for value in (None, 1.0, (), [], 2):
            with pytest.raises(TypeError):
                ITerm2Image._check_style_args({"method": value})
        for value in ("", " ", "cool"):
            with pytest.raises(ValueError):
                ITerm2Image._check_style_args({"method": value})

        for value in (LINES, WHOLE):
            assert ITerm2Image._check_style_args({"method": value}) == {"method": value}
        assert ITerm2Image._check_style_args({"native": False}) == {}
        assert ITerm2Image._check_style_args({"native": True}) == {"native": True}

    def test_mix(self):
        for value in (0, 1.0, (), [], "2"):
            with pytest.raises(TypeError):
                ITerm2Image._check_style_args({"mix": value})

        assert ITerm2Image._check_style_args({"mix": False}) == {}
        assert ITerm2Image._check_style_args({"mix": True}) == {"mix": True}

    def test_compress(self):
        for value in (1.0, (), [], "2"):
            with pytest.raises(TypeError):
                ITerm2Image._check_style_args({"compress": value})
        for value in (-1, 10):
            with pytest.raises(ValueError):
                ITerm2Image._check_style_args({"compress": value})

        assert ITerm2Image._check_style_args({"compress": 4}) == {}
        for value in range(1, 10):
            if value != 4:
                assert (
                    ITerm2Image._check_style_args({"compress": value})
                    == {"compress": value}  # fmt: skip
                )
