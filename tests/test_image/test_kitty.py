"""KittyImage-specific tests"""

import io
from base64 import standard_b64decode
from contextlib import contextmanager
from zlib import decompress

import pytest

from term_image import _ctlseqs as ctlseqs
from term_image.color import Color
from term_image.exceptions import StyleError
from term_image.image import kitty
from term_image.image.kitty import LINES, WHOLE, KittyImage

from .. import set_fg_bg_colors
from . import common
from .common import _size, get_actual_render_size, python_img, setup_common


def test_setup_common():
    setup_common(KittyImage)


for name, obj in vars(common).items():
    if name.endswith(("_All", "_Graphics")):
        globals()[name] = obj


def test_set_render_method():
    try:
        assert KittyImage._render_method == KittyImage._default_render_method == LINES
        image = KittyImage(python_img)
        assert image._render_method == KittyImage._default_render_method

        # Case-insensitivity
        assert KittyImage.set_render_method(WHOLE.upper()) is None
        assert KittyImage.set_render_method(WHOLE.lower()) is None
        assert KittyImage.set_render_method(LINES.upper()) is None
        assert KittyImage.set_render_method(LINES.lower()) is None

        assert KittyImage.set_render_method(WHOLE) is None
        assert KittyImage._render_method == WHOLE
        assert image._render_method == WHOLE

        assert image.set_render_method(LINES) is None
        assert image._render_method == LINES

        assert image.set_render_method() is None
        assert image._render_method == WHOLE

        assert KittyImage.set_render_method(LINES) is None
        assert KittyImage._render_method == LINES
        assert image._render_method == LINES

        assert image.set_render_method(WHOLE) is None
        assert image._render_method == WHOLE

        assert image.set_render_method() is None
        assert image._render_method == LINES

        assert KittyImage.set_render_method(WHOLE) is None
        assert KittyImage._render_method == WHOLE
        assert image._render_method == WHOLE

        assert KittyImage.set_render_method() is None
        assert KittyImage._render_method == KittyImage._default_render_method
        assert image._render_method == KittyImage._default_render_method
    finally:
        KittyImage._render_method = KittyImage._default_render_method


def test_style_format_spec():
    for spec in (
        " ",
        "x",
        "zz",
        "m0z1",
        "0z",
        "m2",
        "m01",
        "c-1",
        "c10",
        "c4m1",
        "z",
        " z1",
        "m0 ",
        "  z1c1  ",
    ):
        with pytest.raises(StyleError, match="format spec"):
            KittyImage._check_style_format_spec(spec, spec)

    for spec, args in (
        ("", {}),
        ("L", {"method": LINES}),
        ("W", {"method": WHOLE}),
        ("z0", {}),
        ("z1", {"z_index": 1}),
        ("z-1", {"z_index": -1}),
        (f"z{2**31 - 1}", {"z_index": 2**31 - 1}),
        (f"z{-(2**31 - 1)}", {"z_index": -(2**31 - 1)}),
        ("m0", {}),
        ("m1", {"mix": True}),
        ("c4", {}),
        ("c0", {"compress": 0}),
        ("c9", {"compress": 9}),
        ("Wz1m1c9", {"method": WHOLE, "z_index": 1, "mix": True, "compress": 9}),
    ):
        assert KittyImage._check_style_format_spec(spec, spec) == args


class TestStyleArgs:
    def test_unknown(self):
        for args in ({"z": 1}, {"m": True}, {" ": None}, {"xxxx": True}):
            with pytest.raises(StyleError, match="Unknown style-specific"):
                KittyImage._check_style_args(args)

    def test_method(self):
        for value in (None, 1.0, (), [], 2):
            with pytest.raises(TypeError):
                KittyImage._check_style_args({"method": value})
        for value in ("", " ", "cool"):
            with pytest.raises(ValueError):
                KittyImage._check_style_args({"method": value})

        for value in (LINES, WHOLE):
            assert KittyImage._check_style_args({"method": value}) == {"method": value}

    def test_z_index(self):
        for value in (None, 1.0, (), [], "2"):
            with pytest.raises(TypeError):
                KittyImage._check_style_args({"z_index": value})
        for value in (-(2**31), 2**31):
            with pytest.raises(ValueError):
                KittyImage._check_style_args({"z_index": value})

        assert KittyImage._check_style_args({"z_index": 0}) == {}
        for value in (1, -1, -(2**31 - 1), 2**31 - 1):
            assert (
                KittyImage._check_style_args({"z_index": value})
                == {"z_index": value}  # fmt: skip
            )

    def test_mix(self):
        for value in (0, 1.0, (), [], "2"):
            with pytest.raises(TypeError):
                KittyImage._check_style_args({"mix": value})

        assert KittyImage._check_style_args({"mix": False}) == {}
        assert KittyImage._check_style_args({"mix": True}) == {"mix": True}

    def test_compress(self):
        for value in (1.0, (), [], "2"):
            with pytest.raises(TypeError):
                KittyImage._check_style_args({"compress": value})
        for value in (-1, 10):
            with pytest.raises(ValueError):
                KittyImage._check_style_args({"compress": value})

        assert KittyImage._check_style_args({"compress": 4}) == {}
        for value in range(1, 10):
            if value != 4:
                assert (
                    KittyImage._check_style_args({"compress": value})
                    == {"compress": value}  # fmt: skip
                )


def expand_control_data(control_data):
    control_data = control_data.split(",")
    control_codes = {tuple(code.split("=")) for code in control_data}
    assert len(control_codes) == len(control_data)

    return control_codes


def decode_image(data):
    empty, start, data = data.partition(ctlseqs.KITTY_START)
    assert empty == ""
    assert start == ctlseqs.KITTY_START

    transmission, end, fill = data.rpartition(ctlseqs.ST)
    assert end == ctlseqs.ST

    control_data, chunked_payload = transmission.split(";", 1)
    control_codes = expand_control_data(control_data)
    assert (
        code in control_codes for code in expand_control_data("a=T,t=d,z=0,o=z,C=1")
    )

    with io.StringIO() as full_payload:
        # Implies every split after the first would've started with KITTY_START
        chunks = chunked_payload.split(ctlseqs.KITTY_START)
        first_chunk = chunks.pop(0)

        if chunks:
            last_chunk = chunks.pop()
            payload, end, empty = first_chunk.partition(ctlseqs.ST)
            assert end == ctlseqs.ST
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
            transmission, end, empty = chunk.partition(ctlseqs.ST)
            assert end == ctlseqs.ST
            assert empty == ""
            control_data, payload = transmission.split(";")
            assert ("m", "1") in expand_control_data(control_data)
            assert len(payload) <= 4096
            assert payload.isprintable() and " " not in payload
            full_payload.write(payload)

        if last_chunk:
            # ST was removed at the beginning
            control_data, payload = last_chunk.split(";")
            assert ("m", "0") in expand_control_data(control_data)
            assert len(payload) <= 4096
            assert payload.isprintable() and " " not in payload
            full_payload.write(payload)

        raw_image = standard_b64decode(full_payload.getvalue().encode())
        if ("o", "z") in control_codes:
            raw_image = decompress(raw_image)

    return control_codes, raw_image, fill


class TestRenderLines:
    # Fully transparent image
    # It's easy to predict it's pixel values
    trans = KittyImage.from_file("tests/images/trans.png")
    trans.height = _size
    trans.set_render_method(LINES)

    def render_image(self, alpha=0.0, *, z=0, m=False, c=4, b=True):
        return self.trans._renderer(
            self.trans._render_image, alpha, z_index=z, mix=m, compress=c, blend=b
        )

    def _test_image_size(self, image):
        w, h = get_actual_render_size(image)
        cols, lines = image.rendered_size
        bytes_per_line = w * (h // lines) * 4
        size_control_data = f"s={w},v={h // lines},c={cols},r=1"
        render = str(image)

        assert render.count("\n") + 1 == lines
        for line in render.splitlines():
            control_codes, raw_image, fill = decode_image(line)
            assert (
                code in control_codes for code in expand_control_data(size_control_data)
            )
            assert len(raw_image) == bytes_per_line
            assert fill == FILL % ((cols,) * 2)

    def test_transmission(self):
        # Not chunked (image data is entirely contiguous, so it's highly compressed)
        # Size is tested in `test_size()`
        for line in self.render_image().splitlines():
            decode_image(line)

        # Chunked (image data is very sparse, so it's still large after compression)
        hori = KittyImage.from_file("tests/images/hori.jpg")
        hori.height = _size
        hori.set_render_method(LINES)
        w, h = get_actual_render_size(hori)
        bytes_per_line = w * (h // self.trans.height) * 3
        for line in str(hori).splitlines():
            assert len(decode_image(line)[1]) == bytes_per_line

    def test_no_minimal_render_size(self):
        image = KittyImage.from_file("tests/images/trans.png")
        image.set_render_method(LINES)
        lines_for_original_height = KittyImage._pixels_lines(
            pixels=image.original_size[1]
        )

        # render size < original size; Uses render size
        image.height = lines_for_original_height // 2
        w, h = image._get_render_size()
        assert get_actual_render_size(image) == (w, h)
        self._test_image_size(image)

        # render size > original size; Uses render size
        image.height = lines_for_original_height * 2
        w, h = image._get_render_size()
        assert get_actual_render_size(image) == (w, h)
        self._test_image_size(image)

    def test_size(self):
        self._test_image_size(self.trans)

    def test_image_data_and_transparency(self):
        w, h = get_actual_render_size(self.trans)
        pixels_per_line = w * (h // _size)

        # Transparency enabled
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1}"
        for line in render.splitlines():
            control_codes, raw_image, _ = decode_image(line)
            assert ("f", "32") in control_codes
            assert len(raw_image) == pixels_per_line * 4
            assert raw_image.count(b"\0" * 4) == pixels_per_line
        # Transparency disabled
        render = self.render_image(None)
        assert render == f"{self.trans:1.1#}"
        for line in render.splitlines():
            control_codes, raw_image, _ = decode_image(line)
            assert ("f", "24") in control_codes
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\0\0\0") == pixels_per_line

    def test_image_data_and_background_colour(self):
        w, h = get_actual_render_size(self.trans)
        pixels_per_line = w * (h // _size)

        # Terminal BG
        for bg in ((0,) * 3, (100,) * 3, (255,) * 3, None):
            set_fg_bg_colors(bg=bg and Color(*bg))
            pixel_bytes = bytes(bg or (0, 0, 0))
            render = self.render_image("#")
            assert render == f"{self.trans:1.1##}"
            for line in render.splitlines():
                control_codes, raw_image, _ = decode_image(line)
                assert ("f", "24") in control_codes
                assert len(raw_image) == pixels_per_line * 3
                assert raw_image.count(pixel_bytes) == pixels_per_line
        set_fg_bg_colors(Color(0, 0, 0), Color(0, 0, 0))
        # red
        render = self.render_image("#ff0000")
        assert render == f"{self.trans:1.1#ff0000}"
        for line in render.splitlines():
            control_codes, raw_image, _ = decode_image(line)
            assert ("f", "24") in control_codes
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\xff\0\0") == pixels_per_line
        # green
        render = self.render_image("#00ff00")
        assert render == f"{self.trans:1.1#00ff00}"
        for line in render.splitlines():
            control_codes, raw_image, _ = decode_image(line)
            assert ("f", "24") in control_codes
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\0\xff\0") == pixels_per_line
        # blue
        render = self.render_image("#0000ff")
        assert render == f"{self.trans:1.1#0000ff}"
        for line in render.splitlines():
            control_codes, raw_image, _ = decode_image(line)
            assert ("f", "24") in control_codes
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\0\0\xff") == pixels_per_line
        # white
        render = self.render_image("#ffffff")
        assert render == f"{self.trans:1.1#ffffff}"
        for line in render.splitlines():
            control_codes, raw_image, _ = decode_image(line)
            assert ("f", "24") in control_codes
            assert len(raw_image) == pixels_per_line * 3
            assert raw_image.count(b"\xff" * 3) == pixels_per_line

    def test_z_index(self):
        # z_index = 0  (default)
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1+z0}"
        for line in render.splitlines():
            assert ("z", "0") in decode_image(line)[0]

        # z_index = <int32_t>
        for value in (1, -1, -(2**31 - 1), 2**31 - 1):
            render = self.render_image(None, z=value)
            assert render == f"{self.trans:1.1#+z{value}}"
            for line in render.splitlines():
                assert ("z", f"{value}") in decode_image(line)[0]

    def test_mix(self):
        # mix = False (default)
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1+m0}"
        for line in render.splitlines():
            fill = decode_image(line)[2]
            assert fill == FILL % ((self.trans.rendered_width,) * 2)

        # mix = True
        render = self.render_image(None, m=True)
        assert render == f"{self.trans:1.1#+m1}"
        for line in render.splitlines():
            fill = decode_image(line)[2]
            assert fill == ctlseqs.CURSOR_FORWARD % self.trans.rendered_width

    def test_compress(self):
        # compress = 4  (default)
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1+c4}"
        for line in render.splitlines():
            assert ("o", "z") in decode_image(line)[0]

        # compress = 0
        render = self.render_image(None, c=0)
        assert render == f"{self.trans:1.1#+c0}"
        for line in render.splitlines():
            assert all(key != "o" for key, value in decode_image(line)[0])

        # compress = {1-9}
        for value in range(1, 10):
            render = self.render_image(None, c=value)
            assert render == f"{self.trans:1.1#+c{value}}"
            for line in render.splitlines():
                assert ("o", "z") in decode_image(line)[0]

        # Image data size relativity
        assert (
            len(self.render_image(c=0))
            > len(self.render_image(c=1))
            > len(self.render_image(c=9))
        )

    def test_blend_false(self):
        render = self.render_image(None, b=False)
        for line in render.splitlines():
            assert line.startswith(ctlseqs.KITTY_DELETE_CURSOR)


class TestRenderWhole:
    # Fully transparent image
    # It's easy to predict it's pixel values
    trans = KittyImage.from_file("tests/images/trans.png")
    trans.height = _size
    trans.set_render_method(WHOLE)

    def render_image(self, alpha=0.0, z=0, m=False, c=4, b=True):
        return self.trans._renderer(
            self.trans._render_image, alpha, z_index=z, mix=m, compress=c, blend=b
        )

    def _test_image_size(self, image):
        w, h = get_actual_render_size(image)
        cols, lines = image.rendered_size
        size_control_data = f"s={w},v={h},c={cols},r={lines}"
        render = str(image)

        assert render.count("\n") + 1 == lines
        control_codes, raw_image, fill = decode_image(render)
        assert (
            code in control_codes for code in expand_control_data(size_control_data)
        )
        assert len(raw_image) == w * h * 4
        assert fill.count("\n") + 1 == lines
        assert (line == FILL % ((cols,) * 2) for line in fill.splitlines())

    def test_transmission(self):
        # Not chunked (image data is entirely contiguous, so it's highly compressed)
        # Image data size is tested in `test_size()`
        decode_image(self.render_image())

        # Chunked (image data is very sparse, so it's still large after compression)
        hori = KittyImage.from_file("tests/images/hori.jpg")
        hori.height = _size
        hori.set_render_method(WHOLE)
        w, h = get_actual_render_size(hori)
        assert len(decode_image(str(hori))[1]) == w * h * 3

    def test_minimal_render_size(self):
        image = KittyImage.from_file("tests/images/trans.png")
        image.set_render_method(WHOLE)
        lines_for_original_height = KittyImage._pixels_lines(
            pixels=image.original_size[1]
        )

        # render size < original size; Uses render size
        image.height = lines_for_original_height // 2
        w, h = image._get_render_size()
        assert get_actual_render_size(image) == (w, h)
        self._test_image_size(image)

        # render size > original size; Uses original size
        image.height = lines_for_original_height * 2
        w, h = image._original_size
        assert get_actual_render_size(image) == (w, h)
        self._test_image_size(image)

    def test_size(self):
        self._test_image_size(self.trans)

    def test_image_data_and_transparency(self):
        w, h = get_actual_render_size(self.trans)

        # Transparency enabled
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1}"
        control_codes, raw_image, _ = decode_image(render)
        assert ("f", "32") in control_codes
        assert len(raw_image) == w * h * 4
        assert raw_image.count(b"\0" * 4) == w * h

        # Transparency disabled
        render = self.render_image(None)
        assert render == f"{self.trans:1.1#}"
        control_codes, raw_image, _ = decode_image(render)
        assert ("f", "24") in control_codes
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\0\0\0") == w * h

    def test_image_data_and_background_colour(self):
        w, h = get_actual_render_size(self.trans)

        # Terminal BG
        for bg in ((0,) * 3, (100,) * 3, (255,) * 3, None):
            set_fg_bg_colors(bg=bg and Color(*bg))
            pixel_bytes = bytes(bg or (0, 0, 0))
            render = self.render_image("#")
            assert render == f"{self.trans:1.1##}"
            control_codes, raw_image, _ = decode_image(render)
            assert ("f", "24") in control_codes
            assert len(raw_image) == w * h * 3
            assert raw_image.count(pixel_bytes) == w * h

        # red
        render = self.render_image("#ff0000")
        assert render == f"{self.trans:1.1#ff0000}"
        control_codes, raw_image, _ = decode_image(render)
        assert ("f", "24") in control_codes
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\xff\0\0") == w * h

        # green
        render = self.render_image("#00ff00")
        assert render == f"{self.trans:1.1#00ff00}"
        control_codes, raw_image, _ = decode_image(render)
        assert ("f", "24") in control_codes
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\0\xff\0") == w * h

        # blue
        render = self.render_image("#0000ff")
        assert render == f"{self.trans:1.1#0000ff}"
        control_codes, raw_image, _ = decode_image(render)
        assert ("f", "24") in control_codes
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\0\0\xff") == w * h

        # white
        render = self.render_image("#ffffff")
        assert render == f"{self.trans:1.1#ffffff}"
        control_codes, raw_image, _ = decode_image(render)
        assert ("f", "24") in control_codes
        assert len(raw_image) == w * h * 3
        assert raw_image.count(b"\xff" * 3) == w * h

    def test_z_index(self):
        # z_index = 0  (default)
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1+z0}"
        assert ("z", "0") in decode_image(render)[0]

        # z_index = <int32_t>
        for value in (1, -1, -(2**31 - 1), 2**31 - 1):
            render = self.render_image(None, z=value)
            assert render == f"{self.trans:1.1#+z{value}}"
            control_codes = decode_image(render)[0]
            assert ("z", f"{value}") in control_codes

    def test_mix(self):
        # mix = False (default)
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1+m0}"
        assert all(
            line == FILL % ((self.trans.rendered_width,) * 2)
            for line in decode_image(render)[2].splitlines()
        )

        # mix = True
        render = self.render_image(None, m=True)
        assert render == f"{self.trans:1.1#+m1}"
        assert all(
            line == ctlseqs.CURSOR_FORWARD % self.trans.rendered_width
            for line in decode_image(render)[2].splitlines()
        )

    def test_compress(self):
        # compress = 4  (default)
        render = self.render_image()
        assert render == str(self.trans) == f"{self.trans:1.1+c4}"
        assert ("o", "z") in decode_image(render)[0]

        # compress = 0
        render = self.render_image(None, c=0)
        assert render == f"{self.trans:1.1#+c0}"
        assert all(key != "o" for key, value in decode_image(render)[0])

        # compress = {1-9}
        for value in range(1, 10):
            render = self.render_image(None, c=value)
            assert render == f"{self.trans:1.1#+c{value}}"
            assert ("o", "z") in decode_image(render)[0]

    def test_blend_false(self):
        render = self.render_image(None, b=False)
        assert render.startswith(ctlseqs.KITTY_DELETE_CURSOR)


class TestClear:
    @contextmanager
    def setup_buffer(self):
        buf = io.StringIO()
        tty_buf = io.BytesIO()

        stdout_write = kitty._stdout_write
        write_tty = kitty.write_tty
        kitty._stdout_write = buf.write
        kitty.write_tty = tty_buf.write

        try:
            yield buf, tty_buf
        finally:
            kitty._stdout_write = stdout_write
            kitty.write_tty = write_tty
            buf.close()
            tty_buf.close()

    def test_args(self):
        for value in (1, 1.1, "1", []):
            with pytest.raises(TypeError, match="'cursor'"):
                KittyImage.clear(cursor=value)

        for value in (1.1, "1", []):
            with pytest.raises(TypeError, match="'z_index'"):
                KittyImage.clear(z_index=value)

        for value in (-(2**31 + 1), 2**31):
            with pytest.raises(ValueError, match="'z_index'"):
                KittyImage.clear(z_index=value)

        for value in (1, 1.1, "1", []):
            with pytest.raises(TypeError, match="'now'"):
                KittyImage.clear(now=value)

        with pytest.raises(ValueError, match="one argument"):
            KittyImage.clear(cursor=True, z_index=0)

    def test_all(self):
        with self.setup_buffer() as (buf, tty_buf):
            KittyImage.clear(now=True)
            assert buf.getvalue() == ""
            assert tty_buf.getvalue() == ctlseqs.KITTY_DELETE_ALL_b

        with self.setup_buffer() as (buf, tty_buf):
            KittyImage.clear()
            assert buf.getvalue() == ctlseqs.KITTY_DELETE_ALL
            assert tty_buf.getvalue() == b""

    def test_cursor(self):
        with self.setup_buffer() as (buf, tty_buf):
            KittyImage.clear(cursor=True, now=True)
            assert buf.getvalue() == ""
            assert tty_buf.getvalue() == ctlseqs.KITTY_DELETE_CURSOR_b

        with self.setup_buffer() as (buf, tty_buf):
            KittyImage.clear(cursor=True)
            assert buf.getvalue() == ctlseqs.KITTY_DELETE_CURSOR
            assert tty_buf.getvalue() == b""

    def test_z_index(self):
        for value in (-(2**31), *range(-10, 11), 2**31 - 1):
            with self.setup_buffer() as (buf, tty_buf):
                KittyImage.clear(z_index=value, now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == ctlseqs.KITTY_DELETE_Z_INDEX_b % value

            with self.setup_buffer() as (buf, tty_buf):
                KittyImage.clear(z_index=value)
                assert buf.getvalue() == ctlseqs.KITTY_DELETE_Z_INDEX % value
                assert tty_buf.getvalue() == b""

    def test_not_supported(self):
        KittyImage._supported = False
        try:
            with self.setup_buffer() as (buf, tty_buf):
                KittyImage.clear()
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

                KittyImage.clear(now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

                KittyImage.clear(cursor=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

                KittyImage.clear(cursor=True, now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

                KittyImage.clear(z_index=0)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

                KittyImage.clear(z_index=0, now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""
        finally:
            KittyImage._supported = True


FILL = ctlseqs.ERASE_CHARS + ctlseqs.CURSOR_FORWARD
