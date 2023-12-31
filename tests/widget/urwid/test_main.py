import gc

import pytest
import urwid
from PIL import Image

from term_image import _ctlseqs as ctlseqs
from term_image.exceptions import RenderError, UrwidImageError
from term_image.image import (
    BlockImage,
    GraphicsImage,
    ITerm2Image,
    KittyImage,
    Size,
    TextImage,
)
from term_image.image.common import _ALPHA_THRESHOLD
from term_image.widget import UrwidImage, UrwidImageCanvas

from ... import get_terminal_name_version, set_terminal_name_version

_size = (30, 15)

python_file = "tests/images/python.png"
python_img = Image.open(python_file)
python_image = BlockImage(python_img)
kitty_image = KittyImage(python_img)
trans = BlockImage.from_file("tests/images/trans.png")


class TestWidget:
    def test_args(self):
        for value in (python_file, python_img):
            with pytest.raises(TypeError, match="'image'"):
                UrwidImage(value)

        for value in (None, 2.0, 2):
            with pytest.raises(TypeError, match="'format_spec'"):
                UrwidImage(python_image, value)
        for string in (".", "+"):
            with pytest.raises(ValueError, match="format specifier"):
                UrwidImage(python_image, string)

        for value in (None, 2.0, "2"):
            with pytest.raises(TypeError, match="'upscale'"):
                UrwidImage(python_image, upscale=value)

    def test_attributes(self):
        image_w = UrwidImage(python_image)
        assert all(name.startswith("_ti_") for name in vars(image_w))

    def test_image(self):
        image_w = UrwidImage(python_image)
        assert image_w.image is python_image

    def test_error_placeholder(self):
        image = BlockImage(Image.new("La", (1, 1)))
        image_w = UrwidImage(image)
        placeholder = urwid.SolidFill("?")

        with pytest.raises(RenderError, match="convert"):
            image_w.render(_size)

        image_w.set_error_placeholder(placeholder)
        canv = image_w.render(_size)
        assert isinstance(canv, urwid.CompositeCanvas)
        assert len(canv.shards) == 1

        solid_canv = canv.shards[0][1][0][-1]
        assert isinstance(solid_canv, urwid.SolidCanvas)
        assert solid_canv.widget_info[0] is placeholder
        assert solid_canv.size == _size


class TestRows:
    def test_upscale_false(self):
        image_w = UrwidImage(python_image)
        ori_size = python_image._valid_size(Size.ORIGINAL)
        fit_size = python_image._valid_size(ori_size[0] - 5)

        assert ori_size[1] != fit_size[1]
        assert image_w.rows((ori_size[0] - 5,)) == fit_size[1]
        assert image_w.rows((ori_size[0] + 5,)) == ori_size[1]

    def test_upscale_true(self):
        image_w = UrwidImage(python_image, upscale=True)
        ori_size = python_image._valid_size(Size.ORIGINAL)

        assert (
            image_w.rows((ori_size[0] - 5,))
            == image_w._ti_image._valid_size(ori_size[0] - 5)[1]
            != ori_size[1]
        )
        assert (
            image_w.rows((ori_size[0] + 5,))
            == image_w._ti_image._valid_size(ori_size[0] + 5)[1]
            != ori_size[1]
        )


class TestRender:
    class TestBox:
        def _test_output(self, canv, size, image_size):
            trans._size = image_size
            render = trans._format_render(
                trans._renderer(
                    trans._render_image, _ALPHA_THRESHOLD, split_cells=True
                ),
                None,
                size[0],
                None,
                size[1],
            ).splitlines()
            lines = canv._ti_lines

            assert canv.size == size
            assert len(lines) == size[1] == len(render)
            for line, render_line in zip(lines, render):
                assert isinstance(line, bytes)
                assert line.decode() == render_line + "\0\0"

        def test_smaller_than_original_size(self):
            not_upscaled = UrwidImage(trans)
            upscaled = UrwidImage(trans, upscale=True)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = tuple((x - 2 for x in ori_size))
            upscaled_canv = upscaled.render(size)
            not_upscaled_canv = not_upscaled.render(size)
            image_size = trans._valid_size(Size.FIT, frame_size=size)

            self._test_output(upscaled_canv, size, image_size)
            self._test_output(not_upscaled_canv, size, image_size)
            assert upscaled_canv._ti_lines == not_upscaled_canv._ti_lines

        def test_upscale_false(self):
            image_w = UrwidImage(trans)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = tuple((x + 2 for x in ori_size))
            canv = image_w.render(size)
            lines = canv._ti_lines

            self._test_output(canv, size, ori_size)

            # One padding line at both the top and bottom
            assert lines[0].rstrip(b"\0\0").isspace()
            assert not lines[1].rstrip(b"\0\0").isspace()
            assert not lines[-2].rstrip(b"\0\0").isspace()
            assert lines[-1].rstrip(b"\0\0").isspace()

            # One padding column on both ends of each line
            for line in lines:
                line = line.decode().rstrip("\0\0")
                if not line.isspace():
                    left, _, right = line.split(ctlseqs.SGR_NORMAL)
                    assert left == " "
                    assert right == " "

        def test_upscale_true(self):
            image_w = UrwidImage(trans, upscale=True)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = trans._valid_size(ori_size[0] + 2)
            canv = image_w.render(size)
            lines = canv._ti_lines
            image_size = trans._valid_size(Size.FIT, frame_size=size)

            # The image should have no padding; *size* is proportional to image size
            # and sizing is FIT.

            self._test_output(canv, size, image_size)
            assert not lines[0].rstrip(b"\0\0").isspace()
            assert not lines[-1].rstrip(b"\0\0").isspace()
            for line in lines:
                line = line.decode().rstrip("\0\0")
                if not line.isspace():
                    left, _, right = line.split(ctlseqs.SGR_NORMAL)
                    assert left == ""
                    assert right == ""

    class TestFlow:
        def _test_output(self, canv, size, image_size, upscaled):
            trans._size = image_size
            render = trans._format_render(
                trans._renderer(
                    trans._render_image, _ALPHA_THRESHOLD, split_cells=True
                ),
                None,
                size[0],
                None,
                1,
            ).splitlines()
            lines = canv._ti_lines

            assert canv.size == (size[0], image_size[1])
            assert len(lines) == image_size[1] == len(render)
            if upscaled:
                assert size[0] == image_size[0]
            for line, render_line in zip(lines, render):
                assert isinstance(line, bytes)
                assert line.decode() == render_line + "\0\0"

        def test_smaller_than_original_size(self):
            not_upscaled = UrwidImage(trans)
            upscaled = UrwidImage(trans, upscale=True)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = (ori_size[0] - 2,)
            upscaled_canv = upscaled.render(size)
            not_upscaled_canv = not_upscaled.render(size)
            image_size = trans._valid_size(size[0])

            self._test_output(upscaled_canv, size, image_size, True)
            self._test_output(not_upscaled_canv, size, image_size, False)
            assert upscaled_canv._ti_lines == not_upscaled_canv._ti_lines

        def test_upscale_false(self):
            image_w = UrwidImage(trans)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = (ori_size[0] + 2,)
            canv = image_w.render(size)
            lines = canv._ti_lines

            self._test_output(canv, size, ori_size, False)

            # No vertical padding
            assert not lines[1].rstrip(b"\0\0").isspace()
            assert not lines[-2].rstrip(b"\0\0").isspace()

            # One padding column on both ends of each line
            for line in lines:
                line = line.decode().rstrip("\0\0")
                if not line.isspace():
                    left, _, right = line.split(ctlseqs.SGR_NORMAL)
                    assert left == " "
                    assert right == " "

        def test_upscale_true(self):
            image_w = UrwidImage(trans, upscale=True)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = (ori_size[0] + 2,)
            canv = image_w.render(size)
            lines = canv._ti_lines

            # The image should have no padding

            self._test_output(canv, size, trans._valid_size(size[0]), True)
            assert not lines[0].rstrip(b"\0\0").isspace()
            assert not lines[-1].rstrip(b"\0\0").isspace()
            for line in lines:
                line = line.decode().rstrip("\0\0")
                if not line.isspace():
                    left, _, right = line.split(ctlseqs.SGR_NORMAL)
                    assert left == ""
                    assert right == ""

    def test_fixed(self):
        image_w = UrwidImage(trans)
        with pytest.raises(UrwidImageError, match="fixed"):
            image_w.render(())


def test_ignore_padding():
    canvases_lines = [
        UrwidImage(python_image, fmt).render(_size)._ti_lines
        for fmt in ("", "200.200", "100.50")
    ]
    python_image.set_size(Size.AUTO, frame_size=_size)
    render = (
        python_image._format_render(
            python_image._renderer(
                python_image._render_image, _ALPHA_THRESHOLD, split_cells=True
            ),
            None,
            _size[0],
            None,
            _size[1],
        )
        .encode()
        .splitlines()
    )

    for render_line, line1, line2, line3 in zip(render, *canvases_lines):
        assert render_line + b"\0\0" == line1 == line2 == line3


# There's no need to test formatting separately since it uses the functionality of the
# underlying image


class TestKittyWidget:
    def test_disguise(self):
        image_w = UrwidImage(kitty_image)
        canv = image_w.render(_size)
        UrwidImageCanvas._ti_disguise_state = 0
        for disguise_state in (0, 1, 2, 0, 1, 2, 0):
            content = canv.text
            for line in content:
                line = line.decode()
                assert line.endswith("\0\0" + "\b " * disguise_state)
            image_w._ti_change_disguise()

    def test_disguise_combined(self):
        image_w = UrwidImage(kitty_image)
        canv = image_w.render(_size)
        UrwidImageCanvas._ti_disguise_state = 2
        try:
            for disguise_states in ((2, 0), (0, 1), (1, 2), (2, 0)):
                content = canv.text
                for line in content:
                    line = line.decode()
                    assert line.endswith("\0\0" + "\b " * sum(disguise_states))
                image_w._ti_change_disguise()
                UrwidImageCanvas._ti_change_disguise()
        finally:
            UrwidImageCanvas._ti_disguise_state = 0

    class TestZIndex:
        def test_alloc(self):
            gc.collect()
            UrwidImage._ti_next_z_index = 1
            UrwidImage._ti_free_z_indexes.clear()
            images = []

            for index in (1, -1, 2, -2, 3, -3, 4, -4):
                images.append(UrwidImage(kitty_image))
                assert images[-1]._ti_z_index == index
            assert UrwidImage._ti_next_z_index == 5

        def test_free(self):
            gc.collect()
            UrwidImage._ti_next_z_index = 1
            UrwidImage._ti_free_z_indexes.clear()

            [UrwidImage(kitty_image) for _ in range(10)]
            gc.collect()

            assert len(UrwidImage._ti_free_z_indexes) == 10
            assert UrwidImage._ti_next_z_index == 6

        def test_use_freed(self):
            gc.collect()
            UrwidImage._ti_next_z_index = 1
            UrwidImage._ti_free_z_indexes.clear()

            images = [UrwidImage(kitty_image) for _ in range(100)]
            z_indexes = {image_w._ti_z_index for image_w in images}
            next_z_index = UrwidImage._ti_next_z_index
            del images
            gc.collect()
            images = [UrwidImage(kitty_image) for _ in range(100)]

            assert {image_w._ti_z_index for image_w in images} == z_indexes
            assert len(UrwidImage._ti_free_z_indexes) == 0
            assert next_z_index == UrwidImage._ti_next_z_index

        def test_limit(self):
            gc.collect()
            UrwidImage._ti_next_z_index = 2**31 - 2
            UrwidImage._ti_free_z_indexes.clear()
            images = []

            for index in (2**31 - 2, -(2**31 - 2), 2**31 - 1, -(2**31 - 1)):
                images.append(UrwidImage(kitty_image))
                assert images[-1]._ti_z_index == index

            with pytest.raises(UrwidImageError, match="many .* kitty"):
                UrwidImage(kitty_image)
            assert UrwidImage._ti_next_z_index == 2**31

            # Does not recover until after a widget is freed
            with pytest.raises(UrwidImageError, match="many .* kitty"):
                UrwidImage(kitty_image)
            assert UrwidImage._ti_next_z_index == 2**31

            del images[0]
            gc.collect()

            # Recovers after a widget is freed
            images.append(UrwidImage(kitty_image))
            assert images[-1]._ti_z_index == 2**31 - 2
            assert UrwidImage._ti_next_z_index == 2**31

            # Fails again after freed index is used
            with pytest.raises(UrwidImageError, match="many .* kitty"):
                UrwidImage(kitty_image)
            assert UrwidImage._ti_next_z_index == 2**31


class TestCanvas:
    def test_cols(self):
        image_w = UrwidImage(python_image, upscale=True)
        canv = image_w.render(_size)
        assert canv.cols() == _size[0]

    def test_rows(self):
        image_w = UrwidImage(python_image, upscale=True)
        canv = image_w.render(_size)
        assert canv.rows() == _size[1]

    def test_content(self):
        image_w = UrwidImage(python_image, upscale=True)
        canv = image_w.render(_size)
        content = canv.text

        assert len(content) == len(canv._ti_lines)
        for content_line, line in zip(content, canv._ti_lines):
            assert content_line == line.replace(b"\0", b"") + b"\0\0"

    def test_disguise_supported(self):
        _terminal_name_version = get_terminal_name_version()
        try:
            set_terminal_name_version("konsole")
            for ImageClass in (KittyImage, ITerm2Image):
                image_w = UrwidImage(ImageClass(python_img))
                canv = image_w.render(_size)

                UrwidImageCanvas._ti_disguise_state = 0
                for disguise_state in (0, 1, 2, 0, 1, 2, 0):
                    content = canv.text
                    for line in content:
                        line = line.decode()
                        assert line.endswith("\0\0" + "\b " * disguise_state)
                    UrwidImageCanvas._ti_change_disguise()
        finally:
            UrwidImageCanvas._ti_disguise_state = 0
            set_terminal_name_version(*_terminal_name_version)

    def test_disguise_not_supported(self):
        _terminal_name_version = get_terminal_name_version()
        try:
            set_terminal_name_version("wezterm")
            for ImageClass in (BlockImage, ITerm2Image):
                image_w = UrwidImage(ImageClass(python_img))
                canv = image_w.render(_size)

                UrwidImageCanvas._ti_disguise_state = 0
                for disguise_state in (0, 1, 2, 0, 1, 2, 0):
                    content = canv.text
                    for line in content:
                        line = line.decode()
                        assert line.endswith("\0\0")
                    UrwidImageCanvas._ti_change_disguise()
        finally:
            UrwidImageCanvas._ti_disguise_state = 0
            set_terminal_name_version(*_terminal_name_version)


def get_trim_render_canv(ImageClass, image_size, h_align, v_align):
    image = ImageClass.from_file("tests/images/trans.png")
    image._size = image_size
    style_args = {"split_cells": True} if issubclass(ImageClass, TextImage) else {}
    render = image._renderer(image._render_image, _ALPHA_THRESHOLD, **style_args)
    image_w = UrwidImage(image, f"{h_align}.{v_align}")
    canv = UrwidImageCanvas(
        image._format_render(render, h_align, _size[0], v_align, _size[1]),
        _size,
        image_size,
    )
    canv._widget_info = (image_w, _size, False)

    pad = _size[0] - image_size[0]
    if h_align == "<":
        pad_left = 0
        pad_right = pad
    elif h_align == ">":
        pad_left = pad
        pad_right = 0
    else:
        pad_left = pad // 2
        pad_right = pad - pad_left

    if issubclass(ImageClass, TextImage):
        pad = _size[1] - image_size[1]
        if v_align == "^":
            pad_top = 0
            pad_bottom = pad
        elif v_align == "_":
            pad_top = pad
            pad_bottom = 0
        else:
            pad_top = pad // 2
            pad_bottom = pad - pad_top

        padding_line = [[b" "] * _size[0]]
        left_padding = [b" "] * pad_left
        right_padding = [b" "] * pad_right

        render = (
            padding_line * pad_top
            + [
                left_padding + line.split(b"\0") + right_padding
                for line in render.encode().split(b"\n")
            ]
            + padding_line * pad_bottom
        )

        return render, canv, pad_top, pad_bottom, pad_left, pad_right
    else:
        render = (
            image._format_render(render, h_align, _size[0], v_align, _size[1])
            .encode()
            .split(b"\n")
        )

        return render, canv


def content_to_text(content_iter):
    return [b"".join(text for *_, text in line) for line in content_iter]


def get_all_trim_args():
    args = (
        (trim_left, trim_top, cols, rows)
        for trim_top in range(0, _size[1], 2)
        for rows in range(_size[1] - trim_top, 0, -2)
        for trim_left in range(0, _size[0], 2)
        for cols in range(_size[0] - trim_left, 0, -2)
        if cols != _size[0]
    )

    return args


def get_hori_trim_args():
    args = (
        (trim_left, cols)
        for trim_left in range(0, _size[0], 2)
        for cols in range(_size[0] - trim_left, 0, -2)
    )
    next(args)  # skip whole canvas

    return args


class TestCanvasTrim:
    class TestCalcTrim:
        # Layout of a formatted render:
        #
        #      A   B      C   D
        #    ->|   |      |   |<-
        #
        # '->' - side1 trim direction
        # A-B  - side1 padding
        # B-C  - image
        # C-D  - side2 padding
        # '<-' - side2 trim direction

        # A=B=0, C=10, D=20
        def test_side1_aligned(self):
            for args, result in (
                # side1 trim at A/B
                ((20, 10, 0, 0, 0, 10), (0, 0, 0, 10)),  # side2 trim at D
                ((20, 10, 0, 0, 2, 10), (0, 0, 0, 8)),  # side2 trim between C and D
                ((20, 10, 0, 0, 10, 10), (0, 0, 0, 0)),  # side2 trim at C
                ((20, 10, 0, 0, 12, 10), (0, 0, 2, 0)),  # side2 trim between B and C
                # side1 trim between B and C
                ((20, 10, 2, 0, 0, 10), (0, 2, 0, 10)),  # side2 trim at D
                ((20, 10, 2, 0, 2, 10), (0, 2, 0, 8)),  # side2 trim between C and D
                ((20, 10, 2, 0, 10, 10), (0, 2, 0, 0)),  # side2 trim at C
                ((20, 10, 2, 0, 12, 10), (0, 2, 2, 0)),  # side2 trim between B and C
                # side1 trim at C
                ((20, 10, 10, 0, 0, 10), (0, 10, 0, 10)),  # side2 trim at D
                ((20, 10, 10, 0, 2, 10), (0, 10, 0, 8)),  # side2 trim between C and D
                # side1 trim between C and D
                ((20, 10, 12, 0, 0, 10), (0, 10, 0, 8)),  # side2 trim at D
                ((20, 10, 12, 0, 2, 10), (0, 10, 0, 6)),  # side2 trim between C and D
            ):
                assert UrwidImageCanvas._ti_calc_trim(*args) == result

        # A=0, B=5, C=15, D=20
        def test_center_aligned(self):
            for args, result in (
                # side1 trim at A
                ((20, 10, 0, 5, 0, 5), (5, 0, 0, 5)),  # side2 trim at D
                ((20, 10, 0, 5, 2, 5), (5, 0, 0, 3)),  # side2 trim between C and D
                ((20, 10, 0, 5, 5, 5), (5, 0, 0, 0)),  # side2 trim at C
                ((20, 10, 0, 5, 7, 5), (5, 0, 2, 0)),  # side2 trim between B and C
                ((20, 10, 0, 5, 15, 5), (5, 0, 10, 0)),  # side2 trim at B
                ((20, 10, 0, 5, 17, 5), (3, 0, 10, 0)),  # side2 trim between A and B
                # side1 trim between A and B
                ((20, 10, 2, 5, 0, 5), (3, 0, 0, 5)),  # side2 trim at D
                ((20, 10, 2, 5, 2, 5), (3, 0, 0, 3)),  # side2 trim between C and D
                ((20, 10, 2, 5, 5, 5), (3, 0, 0, 0)),  # side2 trim at C
                ((20, 10, 2, 5, 7, 5), (3, 0, 2, 0)),  # side2 trim between B and C
                ((20, 10, 2, 5, 15, 5), (3, 0, 10, 0)),  # side2 trim at B
                ((20, 10, 2, 5, 17, 5), (1, 0, 10, 0)),  # side2 trim between A and B
                # side1 trim at B
                ((20, 10, 5, 5, 0, 5), (0, 0, 0, 5)),  # side2 trim at D
                ((20, 10, 5, 5, 2, 5), (0, 0, 0, 3)),  # side2 trim between C and D
                ((20, 10, 5, 5, 5, 5), (0, 0, 0, 0)),  # side2 trim at C
                ((20, 10, 5, 5, 7, 5), (0, 0, 2, 0)),  # side2 trim between B and C
                # side1 trim between B and C
                ((20, 10, 7, 5, 0, 5), (0, 2, 0, 5)),  # side2 trim at D
                ((20, 10, 7, 5, 2, 5), (0, 2, 0, 3)),  # side2 trim between C and D
                ((20, 10, 7, 5, 5, 5), (0, 2, 0, 0)),  # side2 trim at C
                ((20, 10, 7, 5, 7, 5), (0, 2, 2, 0)),  # side2 trim between B and C
                # side1 trim at C
                ((20, 10, 15, 5, 0, 5), (0, 10, 0, 5)),  # side2 trim at D
                ((20, 10, 15, 5, 2, 5), (0, 10, 0, 3)),  # side2 trim between C and D
                # side1 trim between C and D
                ((20, 10, 17, 5, 0, 5), (0, 10, 0, 3)),  # side2 trim at D
                ((20, 10, 17, 5, 2, 5), (0, 10, 0, 1)),  # side2 trim between C and D
            ):
                assert UrwidImageCanvas._ti_calc_trim(*args) == result

        # A=0, B=10, C=D=20
        def test_side2_aligned(self):
            for args, result in (
                # side1 trim at A
                ((20, 10, 0, 10, 0, 0), (10, 0, 0, 0)),  # side2 trim at C/D
                ((20, 10, 0, 10, 2, 0), (10, 0, 2, 0)),  # side2 trim between B and C
                ((20, 10, 0, 10, 10, 0), (10, 0, 10, 0)),  # side2 trim at B
                ((20, 10, 0, 10, 12, 0), (8, 0, 10, 0)),  # side2 trim between A and B
                # side1 trim between A and B
                ((20, 10, 2, 10, 0, 0), (8, 0, 0, 0)),  # side2 trim at C/D
                ((20, 10, 2, 10, 2, 0), (8, 0, 2, 0)),  # side2 trim between B and C
                ((20, 10, 2, 10, 10, 0), (8, 0, 10, 0)),  # side2 trim at B
                ((20, 10, 2, 10, 12, 0), (6, 0, 10, 0)),  # side2 trim between A and B
                # side1 trim at B
                ((20, 10, 10, 10, 0, 0), (0, 0, 0, 0)),  # side2 trim at C/D
                ((20, 10, 10, 10, 2, 0), (0, 0, 2, 0)),  # side2 trim between B and C
                # side1 trim between B and C
                ((20, 10, 12, 10, 0, 0), (0, 2, 0, 0)),  # side2 trim at C/D
                ((20, 10, 12, 10, 2, 0), (0, 2, 2, 0)),  # side2 trim between B and C
            ):
                assert UrwidImageCanvas._ti_calc_trim(*args) == result

    class TestVertical:
        def _test(self, ImageClass, h_align, v_align, graphics=False):
            render, canv, *_ = get_trim_render_canv(
                ImageClass, (_size[0] - 10, _size[1] - 10), h_align, v_align
            )

            for trim_top, rows in (
                (trim, rows)
                for trim in range(1, _size[1])
                for rows in range(_size[1] - trim, 0, -1)
            ):
                # print(trim_top, rows)
                render_text = [
                    line if graphics else b"".join(line)
                    for line in render[trim_top : trim_top + rows]
                ]
                canv_text = content_to_text(canv.content(0, trim_top, None, rows))

                assert len(render_text) == len(canv_text)
                for render_line, canv_line in zip(render_text, canv_text):
                    render_line += b"\0\0"
                    assert len(render_line) == len(canv_line)
                    assert render_line == canv_line

        def test_top_left_aligned_Text(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "<", "^")

        def test_top_center_aligned_Text(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "|", "^")

        def test_top_right_aligned_Text(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, ">", "^")

        def test_middle_left_aligned_Text(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "<", "-")

        def test_middle_center_aligned_Text(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "|", "-")

        def test_middle_right_aligned_Text(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, ">", "-")

        def test_bottom_left_aligned_Text(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "<", "_")

        def test_bottom_center_aligned_Text(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "|", "_")

        def test_bottom_right_aligned_Text(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, ">", "_")

        def test_top_left_aligned_Graphics(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "<", "^", graphics=True)

        def test_top_center_aligned_Graphics(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "|", "^", graphics=True)

        def test_top_right_aligned_Graphics(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, ">", "^", graphics=True)

        def test_middle_left_aligned_Graphics(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "<", "-", graphics=True)

        def test_middle_center_aligned_Graphics(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "|", "-", graphics=True)

        def test_middle_right_aligned_Graphics(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, ">", "-", graphics=True)

        def test_bottom_left_aligned_Graphics(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "<", "_", graphics=True)

        def test_bottom_center_aligned_Graphics(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "|", "_", graphics=True)

        def test_bottom_right_aligned_Graphics(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, ">", "_", graphics=True)

    class TestHorizontalText:
        def _test(self, ImageClass, h_align, v_align):
            (
                render,
                canv,
                pad_top,
                pad_bottom,
                pad_left,
                pad_right,
            ) = get_trim_render_canv(
                ImageClass, (_size[0] - 10, _size[1] - 10), h_align, v_align
            )

            for trim_left, cols in get_hori_trim_args():
                # print(trim_left, cols)
                trim_right = _size[0] - trim_left - cols
                render_text = [
                    b"".join(line[trim_left : trim_left + cols]) for line in render
                ]
                canv_text = content_to_text(canv.content(trim_left, 0, cols))
                prefix = ctlseqs.SGR_NORMAL_b * (
                    pad_left < trim_left < _size[0] - pad_right
                )
                suffix = ctlseqs.SGR_NORMAL_b * (
                    _size[0] - pad_left > trim_right > pad_right
                )

                assert len(render_text) == len(canv_text)

                row = 0
                for render_line, canv_line in zip(render_text, canv_text):
                    # Exclude padding lines
                    if pad_top <= row < _size[1] - pad_bottom:
                        render_line = prefix + render_line + suffix
                    render_line += b"\0\0"
                    row += 1

                    assert len(render_line) == len(canv_line)
                    assert render_line == canv_line

        def test_top_left_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "<", "^")

        def test_top_center_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "|", "^")

        def test_top_right_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, ">", "^")

        def test_middle_left_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "<", "-")

        def test_middle_center_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "|", "-")

        def test_middle_right_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, ">", "-")

        def test_bottom_left_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "<", "_")

        def test_bottom_center_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "|", "_")

        def test_bottom_right_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, ">", "_")

    class TestHorizontalGraphics:
        def _test(self, ImageClass, h_align, v_align):
            render, canv = get_trim_render_canv(
                ImageClass, (_size[0] - 10, _size[1] - 10), h_align, v_align
            )

            for trim_left, cols in get_hori_trim_args():
                # print(trim_left, cols)
                render_text = [b" " * cols] * _size[1]
                canv_text = content_to_text(canv.content(trim_left, 0, cols))

                assert len(render_text) == len(canv_text)
                for render_line, canv_line in zip(render_text, canv_text):
                    assert len(render_line) == len(canv_line)
                    assert render_line == canv_line

        def test_top_left_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "<", "^")

        def test_top_center_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "|", "^")

        def test_top_right_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, ">", "^")

        def test_middle_left_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "<", "-")

        def test_middle_center_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "|", "-")

        def test_middle_right_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, ">", "-")

        def test_bottom_left_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "<", "_")

        def test_bottom_center_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "|", "_")

        def test_bottom_right_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, ">", "_")

    class TestBothText:
        def _test(self, ImageClass, h_align, v_align):
            (
                render,
                canv,
                pad_top,
                pad_bottom,
                pad_left,
                pad_right,
            ) = get_trim_render_canv(
                ImageClass, (_size[0] - 10, _size[1] - 10), h_align, v_align
            )

            for trim_left, trim_top, cols, rows in get_all_trim_args():
                # print(trim_left, trim_top, cols, rows)
                trim_right = _size[0] - trim_left - cols
                render_text = [
                    b"".join(line[trim_left : trim_left + cols])
                    for line in render[trim_top : trim_top + rows]
                ]
                canv_text = content_to_text(
                    canv.content(trim_left, trim_top, cols, rows)
                )
                prefix = ctlseqs.SGR_NORMAL_b * (
                    pad_left < trim_left < _size[0] - pad_right
                )
                suffix = ctlseqs.SGR_NORMAL_b * (
                    _size[0] - pad_left > trim_right > pad_right
                )

                assert len(render_text) == len(canv_text)

                row = trim_top
                for render_line, canv_line in zip(render_text, canv_text):
                    # Exclude padding lines
                    if pad_top <= row < _size[1] - pad_bottom:
                        render_line = prefix + render_line + suffix
                    render_line += b"\0\0"
                    row += 1

                    assert len(render_line) == len(canv_line)
                    assert render_line == canv_line

        def test_top_left_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "<", "^")

        def test_top_center_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "|", "^")

        def test_top_right_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, ">", "^")

        def test_middle_left_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "<", "-")

        def test_middle_center_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "|", "-")

        def test_middle_right_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, ">", "-")

        def test_bottom_left_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "<", "_")

        def test_bottom_center_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, "|", "_")

        def test_bottom_right_aligned(self):
            for cls in TextImage.__subclasses__():
                self._test(cls, ">", "_")

    class TestBothGraphics:
        def _test(self, ImageClass, h_align, v_align):
            render, canv = get_trim_render_canv(
                ImageClass, (_size[0] - 10, _size[1] - 10), h_align, v_align
            )

            for trim_left, trim_top, cols, rows in get_all_trim_args():
                # print(trim_left, trim_top, cols, rows)
                render_text = [b" " * cols] * rows
                canv_text = content_to_text(
                    canv.content(trim_left, trim_top, cols, rows)
                )

                assert len(render_text) == len(canv_text)
                for render_line, canv_line in zip(render_text, canv_text):
                    assert len(render_line) == len(canv_line)
                    assert render_line == canv_line

        def test_top_left_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "<", "^")

        def test_top_center_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "|", "^")

        def test_top_right_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, ">", "^")

        def test_middle_left_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "<", "-")

        def test_middle_center_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "|", "-")

        def test_middle_right_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, ">", "-")

        def test_bottom_left_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "<", "_")

        def test_bottom_center_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, "|", "_")

        def test_bottom_right_aligned(self):
            for cls in GraphicsImage.__subclasses__():
                self._test(cls, ">", "_")

    def test_horizontal_trim_first_color_ColoredText(self):
        for ImageClass in TextImage.__subclasses__():
            image = ImageClass.from_file("tests/images/trans.png")
            image._size = _size
            render = image._renderer(image._render_image, "#102030", split_cells=True)
            image_w = UrwidImage(image, "#102030")
            canv = UrwidImageCanvas(render, _size, _size)
            canv._widget_info = (image_w, _size, False)

            for trim_left in range(1, _size[0]):
                text = content_to_text(
                    canv.content(trim_left, cols=_size[0] - trim_left)
                )
                for line in text:
                    assert line.startswith(
                        ctlseqs.SGR_BG_DIRECT_b % (16, 32, 48) + b" "
                    )
