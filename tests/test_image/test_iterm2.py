"""ITerm2Image-specific tests"""

import io
import sys
from base64 import standard_b64decode
from contextlib import contextmanager
from random import random

import pytest
from PIL import Image
from PIL.GifImagePlugin import GifImageFile
from PIL.PngImagePlugin import PngImageFile

from term_image.exceptions import ITerm2ImageError, TermImageWarning
from term_image.image import iterm2
from term_image.image.iterm2 import LINES, START, WHOLE, ITerm2Image
from term_image.utils import CSI, ST

from .. import set_fg_bg_colors
from . import common
from .common import _size, get_actual_render_size, python_img, setup_common
from .test_base import clear_stdout, stdout

ITerm2Image.READ_FROM_FILE = False

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


def expand_control_data(control_data):
    control_data = control_data.split(";")
    control_codes = {tuple(code.split("=")) for code in control_data}
    assert len(control_codes) == len(control_data)

    return control_codes


def decode_image(data, term="", jpeg=False, native=False, read_from_file=False):
    fill_1, start, data = data.partition(START)
    assert start == START
    if term == "konsole":
        assert fill_1 == ""

    transmission, end, fill_2 = data.rpartition(ST)
    assert end == ST
    if term != "konsole":
        assert fill_2 == ""

    control_data, payload = transmission.split(":", 1)
    control_codes = expand_control_data(control_data)
    assert (
        code in control_codes
        for code in expand_control_data(
            "preserveAspectRatio=0;inline=1"
            + ";doNotMoveCursor=1" * (term == "konsole")
        )
    )

    compressed_image = standard_b64decode(payload.encode())
    img = Image.open(io.BytesIO(compressed_image))
    if native:
        assert isinstance(img, (GifImageFile, PngImageFile))
        assert img.is_animated

    if read_from_file or native:
        raw_image = None
    else:
        raw_image = img.tobytes()
        if jpeg and img.mode != "RGBA":
            assert img.format == "JPEG"
            assert img.mode == "RGB"
        else:
            assert img.format == "PNG"
            assert img.mode in {"RGB", "RGBA"}

    return (
        control_codes,
        img.format,
        img.mode,
        compressed_image,
        raw_image,
        fill_2 if term == "konsole" else fill_1,
    )


class TestRenderLines:
    # Fully transparent image
    # It's easy to predict it's pixel values
    trans = ITerm2Image.from_file("tests/images/trans.png")
    trans.height = _size
    trans.set_render_method(LINES)

    def render_image(self, alpha=0.0, *, m=False, c=4):
        return self.trans._renderer(self.trans._render_image, alpha, mix=m, compress=c)

    @staticmethod
    def _test_image_size(image, term="", jpeg=False):
        w, h = get_actual_render_size(image)
        cols, lines = image.rendered_size
        pixels_per_line = w * (h // lines)
        size_control_data = f"width={cols},height=1"
        render = str(image)

        assert render.count("\n") + 1 == lines
        for n, line in enumerate(render.splitlines(), 1):
            control_codes, format, mode, _, raw_image, fill = decode_image(
                line, term=term, jpeg=jpeg
            )
            assert (
                code in control_codes for code in expand_control_data(size_control_data)
            )
            assert len(raw_image) == pixels_per_line * len(mode)
            assert fill == (
                jump_right.format(cols=cols)
                if term == "konsole"
                else erase.format(cols=cols)
                if term == "wezterm"
                else ""
            )

    def test_minimal_render_size(self):
        image = ITerm2Image.from_file("tests/images/trans.png")
        image.set_render_method(LINES)
        lines_for_original_height = ITerm2Image._pixels_lines(
            pixels=image.original_size[1]
        )

        # Using render size
        image.height = lines_for_original_height // 2
        w, h = image._get_render_size()
        assert get_actual_render_size(image) == (w, h)
        for ITerm2Image._TERM in supported_terminals:
            self._test_image_size(image, term=ITerm2Image._TERM)

        # Using original size
        image.height = lines_for_original_height * 2
        w, h = image._original_size
        extra = h % (image.height or 1)
        if extra:
            h = h - extra + image.height
        assert get_actual_render_size(image) == (w, h)
        for ITerm2Image._TERM in supported_terminals:
            self._test_image_size(image, term=ITerm2Image._TERM)

    def test_size(self):
        self.trans.scale = 1.0
        for ITerm2Image._TERM in supported_terminals:
            self._test_image_size(self.trans, term=ITerm2Image._TERM)

    def test_raw_image_and_transparency(self):
        ITerm2Image._TERM = ""
        self.trans.scale = 1.0
        w, h = get_actual_render_size(self.trans)
        pixels_per_line = w * (h // _size)

        # Transparency enabled
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1}"
        for line in render.splitlines():
            _, format, mode, _, raw_image, _ = decode_image(line)
            assert format == "PNG"
            assert mode == "RGBA"
            assert len(raw_image) == pixels_per_line * 4
            assert raw_image.count(b"\0" * 4) == pixels_per_line
        # Transparency disabled
        render = self.render_image(None)
        assert render == f"{self.trans:1.1#}"
        for line in render.splitlines():
            _, format, mode, _, raw_image, _ = decode_image(line)
            assert format == "PNG"
            assert mode == "RGB"
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\0\0\0") == pixels_per_line

    def test_raw_image_and_background_colour(self):
        ITerm2Image._TERM = ""
        self.trans.scale = 1.0
        w, h = get_actual_render_size(self.trans)
        pixels_per_line = w * (h // _size)

        # Terminal BG
        for bg in ((0,) * 3, (100,) * 3, (255,) * 3, None):
            set_fg_bg_colors(bg=bg)
            pixel_bytes = bytes(bg or (0, 0, 0))
            render = self.render_image("#")
            assert render == f"{self.trans:1.1##}"
            for line in render.splitlines():
                _, format, mode, _, raw_image, _ = decode_image(line)
                assert format == "PNG"
                assert mode == "RGB"
                assert len(raw_image) == pixels_per_line * 3
                assert raw_image.count(pixel_bytes) == pixels_per_line
        # red
        render = self.render_image("#ff0000")
        assert render == f"{self.trans:1.1#ff0000}"
        for line in render.splitlines():
            _, format, mode, _, raw_image, _ = decode_image(line)
            assert format == "PNG"
            assert mode == "RGB"
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\xff\0\0") == pixels_per_line
        # green
        render = self.render_image("#00ff00")
        assert render == f"{self.trans:1.1#00ff00}"
        for line in render.splitlines():
            _, format, mode, _, raw_image, _ = decode_image(line)
            assert format == "PNG"
            assert mode == "RGB"
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\0\xff\0") == pixels_per_line
        # blue
        render = self.render_image("#0000ff")
        assert render == f"{self.trans:1.1#0000ff}"
        for line in render.splitlines():
            _, format, mode, _, raw_image, _ = decode_image(line)
            assert format == "PNG"
            assert mode == "RGB"
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\0\0\xff") == pixels_per_line
        # white
        render = self.render_image("#ffffff")
        assert render == f"{self.trans:1.1#ffffff}"
        for line in render.splitlines():
            _, format, mode, _, raw_image, _ = decode_image(line)
            assert format == "PNG"
            assert mode == "RGB"
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\xff" * 3) == pixels_per_line

    def test_mix(self):
        ITerm2Image._TERM = ""
        self.trans.scale = 1.0
        cols = self.trans.rendered_width

        for ITerm2Image._TERM in supported_terminals:
            # mix = False (default)
            render = self.render_image()
            assert render == str(self.trans) == f"{self.trans:1.1+m0}"
            for line in render.splitlines():
                assert decode_image(line, term=ITerm2Image._TERM)[-1] == (
                    jump_right.format(cols=cols)
                    if ITerm2Image._TERM == "konsole"
                    else erase.format(cols=cols)
                    if ITerm2Image._TERM == "wezterm"
                    else ""
                )

            # mix = True
            render = self.render_image(None, m=True)
            assert render == f"{self.trans:1.1#+m1}"
            for line in render.splitlines():
                assert decode_image(line, term=ITerm2Image._TERM)[-1] == (
                    jump_right.format(cols=cols)
                    if ITerm2Image._TERM == "konsole"
                    else ""
                )

    def test_compress(self):
        ITerm2Image._TERM = ""
        self.trans.scale = 1.0

        # compress = 4  (default)
        assert self.render_image() == str(self.trans) == f"{self.trans:1.1+c4}"
        # compress = 0
        assert self.render_image(None, c=0) == f"{self.trans:1.1#+c0}"
        # compress = {1-9}
        for value in range(1, 10):
            assert self.render_image(None, c=value) == f"{self.trans:1.1#+c{value}}"

        # Data size relativity
        assert (
            len(self.render_image(c=0))
            > len(self.render_image(c=1))
            > len(self.render_image(c=9))
        )

    def test_scaled(self):
        # At varying scales
        for self.trans.scale in map(lambda x: x / 100, range(10, 101, 10)):
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(self.trans, term=ITerm2Image._TERM)

        # Random scales
        for _ in range(20):
            scale = random()
            if scale == 0.0:
                continue
            self.trans.scale = scale
            if 0 in self.trans.rendered_size:
                continue
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(self.trans, term=ITerm2Image._TERM)

    def test_jpeg(self):
        png_image = ITerm2Image.from_file("tests/images/trans.png")
        jpeg_image = ITerm2Image.from_file("tests/images/vert.jpg")
        png_image.set_render_method(LINES)
        jpeg_image.set_render_method(LINES)
        try:
            ITerm2Image.JPEG_QUALITY = 95
            ITerm2Image._TERM = ""

            # Will use PNG since the image has alpha
            lines_for_original_height = ITerm2Image._pixels_lines(
                pixels=png_image.original_size[1]
            )
            png_image.height = lines_for_original_height * 2
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(png_image, term=ITerm2Image._TERM)
                for line in str(png_image).splitlines():
                    _, format, mode, *_ = decode_image(line, term=ITerm2Image._TERM)
                    assert format == "PNG"
                    assert mode == "RGBA"

            # Will use JPEG since the image has no alpha
            lines_for_original_height = ITerm2Image._pixels_lines(
                pixels=jpeg_image.original_size[1]
            )
            jpeg_image.height = lines_for_original_height * 2
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(jpeg_image, term=ITerm2Image._TERM, jpeg=True)
                for line in str(jpeg_image).splitlines():
                    _, format, mode, *_ = decode_image(
                        line, term=ITerm2Image._TERM, jpeg=True
                    )
                    assert format == "JPEG"
                    assert mode == "RGB"

            # Will use JPEG since transparency is disabled
            lines_for_original_height = ITerm2Image._pixels_lines(
                pixels=jpeg_image.original_size[1]
            )
            jpeg_image.height = lines_for_original_height * 2
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(png_image, term=ITerm2Image._TERM, jpeg=True)
                for line in f"{png_image:1.1#}".splitlines():
                    _, format, mode, *_ = decode_image(
                        line, term=ITerm2Image._TERM, jpeg=True
                    )
                    assert format == "JPEG"
                    assert mode == "RGB"

            # Compresssion level / Image data size
            ITerm2Image.JPEG_QUALITY = 0
            jpeg_0 = str(jpeg_image)
            ITerm2Image.JPEG_QUALITY = 50
            jpeg_50 = str(jpeg_image)
            ITerm2Image.JPEG_QUALITY = 95
            jpeg_95 = str(jpeg_image)
            assert len(jpeg_0) < len(jpeg_50) < len(jpeg_95)
        finally:
            ITerm2Image.JPEG_QUALITY = -1


class TestRenderWhole:
    # Fully transparent image
    # It's easy to predict it's pixel values
    trans = ITerm2Image.from_file("tests/images/trans.png")
    trans.height = _size
    trans.set_render_method(WHOLE)

    def render_image(self, alpha=0.0, *, m=False, c=4):
        return self.trans._renderer(self.trans._render_image, alpha, mix=m, compress=c)

    @staticmethod
    def _test_image_size(
        image, term="", jpeg=False, native=False, read_from_file=False
    ):
        w, h = get_actual_render_size(image)
        cols, lines = image.rendered_size
        size_control_data = f"width={cols},height={lines}"
        render = f"{image:1.1+N}" if native else str(image)

        assert render.count("\n") + 1 == lines
        control_codes, format, mode, _, raw_image, fill = decode_image(
            render, term=term, jpeg=jpeg, native=native, read_from_file=read_from_file
        )
        assert (
            code in control_codes for code in expand_control_data(size_control_data)
        )
        if not (read_from_file or native):
            assert len(raw_image) == w * h * len(mode)
        assert fill.count("\n") + 1 == lines
        *fills, last_fill = fill.splitlines()
        assert all(
            line
            == (
                erase.format(cols=cols) * (term == "wezterm")
                + jump_right.format(cols=cols)
            )
            for line in fills
        )
        assert last_fill == (
            jump_right.format(cols=cols)
            if term == "konsole"
            else erase.format(cols=cols) * (term == "wezterm") + f"{CSI}{lines - 1}A"
        )

    def test_minimal_render_size(self):
        image = ITerm2Image.from_file("tests/images/trans.png")
        image.set_render_method(WHOLE)
        lines_for_original_height = ITerm2Image._pixels_lines(
            pixels=image.original_size[1]
        )

        # Using render size
        image.height = lines_for_original_height // 2
        w, h = image._get_render_size()
        assert get_actual_render_size(image) == (w, h)
        for ITerm2Image._TERM in supported_terminals:
            self._test_image_size(image, term=ITerm2Image._TERM)

        # Using original size
        image.height = lines_for_original_height * 2
        w, h = image._original_size
        assert get_actual_render_size(image) == (w, h)
        for ITerm2Image._TERM in supported_terminals:
            self._test_image_size(image, term=ITerm2Image._TERM)

    def test_size(self):
        self.trans.scale = 1.0
        for ITerm2Image._TERM in supported_terminals:
            self._test_image_size(self.trans, term=ITerm2Image._TERM)

    def test_raw_image_and_transparency(self):
        ITerm2Image._TERM = ""
        self.trans.scale = 1.0
        w, h = get_actual_render_size(self.trans)

        # Transparency enabled
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1}"
        _, format, mode, _, raw_image, _ = decode_image(render)
        assert format == "PNG"
        assert mode == "RGBA"
        assert len(raw_image) == w * h * 4
        assert raw_image.count(b"\0" * 4) == w * h

        # Transparency disabled
        render = self.render_image(None)
        assert render == f"{self.trans:1.1#}"
        _, format, mode, _, raw_image, _ = decode_image(render)
        assert format == "PNG"
        assert mode == "RGB"
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\0\0\0") == w * h

    def test_raw_image_and_background_colour(self):
        ITerm2Image._TERM = ""
        self.trans.scale = 1.0
        w, h = get_actual_render_size(self.trans)

        # Terminal BG
        for bg in ((0,) * 3, (100,) * 3, (255,) * 3, None):
            set_fg_bg_colors(bg=bg)
            pixel_bytes = bytes(bg or (0, 0, 0))
            render = self.render_image("#")
            assert render == f"{self.trans:1.1##}"
            _, format, mode, _, raw_image, _ = decode_image(render)
            assert format == "PNG"
            assert mode == "RGB"
            assert len(raw_image) == w * h * 3
            assert raw_image.count(pixel_bytes) == w * h

        # red
        render = self.render_image("#ff0000")
        assert render == f"{self.trans:1.1#ff0000}"
        _, format, mode, _, raw_image, _ = decode_image(render)
        assert format == "PNG"
        assert mode == "RGB"
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\xff\0\0") == w * h

        # green
        render = self.render_image("#00ff00")
        assert render == f"{self.trans:1.1#00ff00}"
        _, format, mode, _, raw_image, _ = decode_image(render)
        assert format == "PNG"
        assert mode == "RGB"
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\0\xff\0") == w * h

        # blue
        render = self.render_image("#0000ff")
        assert render == f"{self.trans:1.1#0000ff}"
        _, format, mode, _, raw_image, _ = decode_image(render)
        assert format == "PNG"
        assert mode == "RGB"
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\0\0\xff") == w * h

        # white
        render = self.render_image("#ffffff")
        assert render == f"{self.trans:1.1#ffffff}"
        _, format, mode, _, raw_image, _ = decode_image(render)
        assert format == "PNG"
        assert mode == "RGB"
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\xff" * 3) == w * h

    def test_mix(self):
        ITerm2Image._TERM = ""
        self.trans.scale = 1.0
        cols, lines = self.trans.rendered_size

        for ITerm2Image._TERM in supported_terminals:
            # mix = False (default)
            render = self.render_image()
            assert render == str(self.trans) == f"{self.trans:1.1+m0}"
            *fills, last_fill = decode_image(
                render, term=ITerm2Image._TERM  # fmt: skip
            )[-1].splitlines()
            assert all(
                line
                == (
                    erase.format(cols=cols) * (ITerm2Image._TERM == "wezterm")
                    + jump_right.format(cols=cols)
                )
                for line in fills
            )
            assert last_fill == (
                jump_right.format(cols=cols)
                if ITerm2Image._TERM == "konsole"
                else (
                    erase.format(cols=cols) * (ITerm2Image._TERM == "wezterm")
                    + f"{CSI}{lines - 1}A"
                )
            )

            # mix = True
            render = self.render_image(None, m=True)
            assert render == f"{self.trans:1.1#+m1}"
            *fills, last_fill = decode_image(
                render, term=ITerm2Image._TERM  # fmt: skip
            )[-1].splitlines()
            assert all(line == jump_right.format(cols=cols) for line in fills)
            assert last_fill == (
                jump_right.format(cols=cols)
                if ITerm2Image._TERM == "konsole"
                else f"{CSI}{lines - 1}A"
            )

    def test_compress(self):
        ITerm2Image._TERM = ""
        self.trans.scale = 1.0

        # compress = 4  (default)
        assert self.render_image() == str(self.trans) == f"{self.trans:1.1+c4}"
        # compress = 0
        assert self.render_image(None, c=0) == f"{self.trans:1.1#+c0}"
        # compress = {1-9}
        for value in range(1, 10):
            assert self.render_image(None, c=value) == f"{self.trans:1.1#+c{value}}"

        # Data size relativity
        assert (
            len(self.render_image(c=0))
            > len(self.render_image(c=1))
            > len(self.render_image(c=9))
        )

    def test_scaled(self):
        # At varying scales
        for self.trans.scale in map(lambda x: x / 100, range(10, 101, 10)):
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(self.trans, term=ITerm2Image._TERM)

        # Random scales
        for _ in range(20):
            scale = random()
            if scale == 0.0:
                continue
            self.trans.scale = scale
            if 0 in self.trans.rendered_size:
                continue
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(self.trans, term=ITerm2Image._TERM)

    def test_jpeg(self):
        png_image = ITerm2Image.from_file("tests/images/trans.png")
        jpeg_image = ITerm2Image.from_file("tests/images/vert.jpg")
        png_image.set_render_method(WHOLE)
        jpeg_image.set_render_method(WHOLE)
        try:
            ITerm2Image.JPEG_QUALITY = 95
            ITerm2Image._TERM = ""

            # Will use PNG since the image has alpha
            lines_for_original_height = ITerm2Image._pixels_lines(
                pixels=png_image.original_size[1]
            )
            png_image.height = lines_for_original_height * 2
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(png_image, term=ITerm2Image._TERM)
                _, format, mode, *_ = decode_image(
                    str(png_image), term=ITerm2Image._TERM
                )
                assert format == "PNG"
                assert mode == "RGBA"

            # Will use JPEG since the image has no alpha
            lines_for_original_height = ITerm2Image._pixels_lines(
                pixels=jpeg_image.original_size[1]
            )
            jpeg_image.height = lines_for_original_height * 2
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(jpeg_image, term=ITerm2Image._TERM, jpeg=True)
                _, format, mode, *_ = decode_image(
                    str(jpeg_image), term=ITerm2Image._TERM, jpeg=True
                )
                assert format == "JPEG"
                assert mode == "RGB"

            # Will use JPEG since transparency is disabled
            lines_for_original_height = ITerm2Image._pixels_lines(
                pixels=jpeg_image.original_size[1]
            )
            jpeg_image.height = lines_for_original_height * 2
            for ITerm2Image._TERM in supported_terminals:
                self._test_image_size(png_image, term=ITerm2Image._TERM, jpeg=True)
                _, format, mode, *_ = decode_image(
                    f"{png_image:1.1#}", term=ITerm2Image._TERM, jpeg=True
                )
                assert format == "JPEG"
                assert mode == "RGB"

            # Compresssion level / Image data size
            ITerm2Image.JPEG_QUALITY = 0
            jpeg_0 = str(jpeg_image)
            ITerm2Image.JPEG_QUALITY = 50
            jpeg_50 = str(jpeg_image)
            ITerm2Image.JPEG_QUALITY = 95
            jpeg_95 = str(jpeg_image)
            assert len(jpeg_0) < len(jpeg_50) < len(jpeg_95)
        finally:
            ITerm2Image.JPEG_QUALITY = -1


def test_read_from_file():
    test_image_size = TestRenderWhole._test_image_size
    png_file = open("tests/images/trans.png", "rb").read()
    png_image = ITerm2Image.from_file("tests/images/trans.png")
    jpeg_file = open("tests/images/vert.jpg", "rb").read()
    jpeg_image = ITerm2Image.from_file("tests/images/vert.jpg")
    png_image.set_render_method(WHOLE)
    jpeg_image.set_render_method(WHOLE)
    try:
        ITerm2Image.READ_FROM_FILE = True
        ITerm2Image._TERM = ""

        # manipulation is required since the mode is RGBA
        lines_for_original_height = ITerm2Image._pixels_lines(
            pixels=png_image.original_size[1]
        )
        png_image.height = lines_for_original_height * 2
        assert png_file != decode_image(f"{png_image:1.1#}", term=ITerm2Image._TERM)[3]

        # manipulation is not required since the mode is RGB
        lines_for_original_height = ITerm2Image._pixels_lines(
            pixels=jpeg_image.original_size[1]
        )
        jpeg_image.height = lines_for_original_height * 2
        assert (
            jpeg_file
            == decode_image(
                f"{jpeg_image:1.1#}", term=ITerm2Image._TERM, read_from_file=True
            )[3]
        )

        for image, file in ((png_image, png_file), (jpeg_image, jpeg_file)):
            lines_for_original_height = ITerm2Image._pixels_lines(
                pixels=image.original_size[1]
            )

            # Will not be downscale
            image.height = lines_for_original_height * 2
            for ITerm2Image._TERM in supported_terminals:
                assert (
                    file
                    == decode_image(
                        str(image), term=ITerm2Image._TERM, read_from_file=True
                    )[3]
                )
                test_image_size(image, term=ITerm2Image._TERM, read_from_file=True)

            # Will be downscaled
            image.height = lines_for_original_height // 2
            for ITerm2Image._TERM in supported_terminals:
                assert file != decode_image(str(image), term=ITerm2Image._TERM)[3]
                test_image_size(image, term=ITerm2Image._TERM)
    finally:
        ITerm2Image.READ_FROM_FILE = False


def test_native_anim():
    def render_native(image):
        return image._renderer(image._render_image, 0.0, native=True)

    test_image_size = TestRenderWhole._test_image_size
    apng_file = open("tests/images/elephant.png", "rb").read()
    apng_image = ITerm2Image.from_file("tests/images/elephant.png", height=_size)
    gif_file = open("tests/images/lion.gif", "rb").read()
    gif_image = ITerm2Image.from_file("tests/images/lion.gif", height=_size)
    webp_file = open("tests/images/anim.webp", "rb").read()
    webp_image = ITerm2Image.from_file("tests/images/anim.webp", height=_size)
    img = Image.open("tests/images/lion.gif")
    img_image = ITerm2Image(img, height=_size)
    no_file_img = Image.open(open("tests/images/lion.gif", "rb"))
    no_file_image = ITerm2Image(no_file_img, height=_size)

    # Reads from file when possible
    for image, file in (
        (apng_image, apng_file),
        (gif_image, gif_file),
        (img_image, gif_file),
    ):
        for ITerm2Image._TERM in ("iterm2", "wezterm"):
            assert (
                file
                == decode_image(
                    render_native(image), term=ITerm2Image._TERM, native=True
                )[3]
            )
            test_image_size(image, term=ITerm2Image._TERM, native=True)

        # Drawing APNG and GIF is supported
        try:
            sys.stdout = stdout
            image.draw(native=True, stall_native=False)
        finally:
            clear_stdout()
            sys.stdout = sys.__stdout__

    # Re-encodes when image file is not accessible
    ITerm2Image._TERM = ""
    for ITerm2Image._TERM in ("iterm2", "wezterm"):
        assert gif_file != decode_image(render_native(no_file_image), native=True)[3]
        test_image_size(no_file_image, term=ITerm2Image._TERM, native=True)

    # No image file an unknown format
    no_file_img.format = None
    with pytest.raises(ITerm2ImageError, match="Native animation .* unknown format"):
        render_native(no_file_image)

    # Konsole does not implement native animation
    ITerm2Image._TERM = "konsole"
    for image in (apng_image, gif_image, webp_image):
        with pytest.raises(
            ITerm2ImageError, match="Native animation .* active terminal"
        ):
            try:
                sys.stdout = stdout
                image.draw(native=True, stall_native=False)
            finally:
                clear_stdout()
                sys.stdout = sys.__stdout__

    # WEBP format is not supported by the terminal emulators
    for ITerm2Image._TERM in ("iterm2", "wezterm"):
        assert (
            webp_file
            != decode_image(render_native(webp_image), term=ITerm2Image._TERM)[3]
        )
        with pytest.raises(ITerm2ImageError, match="Native WEBP animation"):
            try:
                sys.stdout = stdout
                webp_image.draw(native=True, stall_native=False)
            finally:
                clear_stdout()
                sys.stdout = sys.__stdout__

    # Image data size limit
    ITerm2Image.NATIVE_ANIM_MAXSIZE = 300000
    with pytest.warns(TermImageWarning, match="maximum for native animation"):
        render_native(apng_image)
    render_native(gif_image)


class TestClear:
    @contextmanager
    def setup_buffer(self):
        buf = io.StringIO()
        tty_buf = io.BytesIO()

        stdout_write = iterm2._stdout_write
        write_tty = iterm2.write_tty
        iterm2._stdout_write = buf.write
        iterm2.write_tty = tty_buf.write

        try:
            yield buf, tty_buf
        finally:
            iterm2._stdout_write = stdout_write
            iterm2.write_tty = write_tty
            buf.close()
            tty_buf.close()

    def test_all(self):
        _TERM = ITerm2Image._TERM
        ITerm2Image._TERM = "konsole"
        try:
            with self.setup_buffer() as (buf, tty_buf):
                ITerm2Image.clear(now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == iterm2.DELETE_ALL_IMAGES_b

            with self.setup_buffer() as (buf, tty_buf):
                ITerm2Image.clear()
                assert buf.getvalue() == iterm2.DELETE_ALL_IMAGES
                assert tty_buf.getvalue() == b""
        finally:
            ITerm2Image._TERM = _TERM

    def test_cursor(self):
        _TERM = ITerm2Image._TERM
        ITerm2Image._TERM = "konsole"
        try:
            with self.setup_buffer() as (buf, tty_buf):
                ITerm2Image.clear(cursor=True, now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == iterm2.DELETE_CURSOR_IMAGES_b

            with self.setup_buffer() as (buf, tty_buf):
                ITerm2Image.clear(cursor=True)
                assert buf.getvalue() == iterm2.DELETE_CURSOR_IMAGES
                assert tty_buf.getvalue() == b""
        finally:
            ITerm2Image._TERM = _TERM

    def test_not_supported(self):
        ITerm2Image._supported = False
        try:
            with self.setup_buffer() as (buf, tty_buf):
                ITerm2Image.clear()
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

                ITerm2Image.clear(cursor=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""
        finally:
            ITerm2Image._supported = True

    def test_not_on_konsole(self):
        _TERM = ITerm2Image._TERM
        try:
            for ITerm2Image._TERM in supported_terminals - {"konsole"}:
                with self.setup_buffer() as (buf, tty_buf):
                    ITerm2Image.clear()
                    assert buf.getvalue() == ""
                    assert tty_buf.getvalue() == b""

                    ITerm2Image.clear(cursor=True)
                    assert buf.getvalue() == ""
                    assert tty_buf.getvalue() == b""
        finally:
            ITerm2Image._TERM = _TERM


supported_terminals = {"iterm2", "wezterm", "konsole"}
erase = f"{CSI}{{cols}}X"
jump_right = f"{CSI}{{cols}}C"
fill_fmt = f"{CSI}{{cols}}X{jump_right}"
