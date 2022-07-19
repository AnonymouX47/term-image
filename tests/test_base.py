"""Render-style-independent tests"""

import io
import os
import sys
from operator import mul
from random import random

import pytest
from PIL import Image, UnidentifiedImageError

from term_image import set_font_ratio
from term_image.exceptions import InvalidSizeError, TermImageError
from term_image.image import BlockImage, ImageIterator, ImageSource, Size
from term_image.image.common import _ALPHA_THRESHOLD
from term_image.utils import ESC

from .common import _size, columns, lines, python_img, setup_common

python_image = "tests/images/python.png"
python_sym = "tests/images/python_sym.png"  # Symlink to "python.png"
anim_img = Image.open("tests/images/lion.gif")
stdout = io.StringIO()

setup_common(BlockImage)
from .common import _height, _width  # noqa:E402


def clear_stdout():
    stdout.seek(0)
    stdout.truncate()


class TestConstructor:
    def test_args(self):
        with pytest.raises(TypeError, match=r"'PIL\.Image\.Image' instance"):
            BlockImage(python_image)

        # Ensure size arguments get through to `set_size()`
        with pytest.raises(ValueError, match=r".* both width and height"):
            BlockImage(python_img, width=1, height=1)

        with pytest.raises(TypeError, match=r"'scale'"):
            BlockImage(python_img, scale=0.5)
        for value in ((0.0, 0.0), (-0.4, -0.4)):
            with pytest.raises(ValueError, match=r"'scale'"):
                BlockImage(python_img, scale=value)

    def test_init(self):
        image = BlockImage(python_img)
        assert image._size is Size.FIT
        assert isinstance(image._scale, list)
        assert image._scale == [1.0, 1.0]
        assert image._source is python_img
        assert image._source_type is ImageSource.PIL_IMAGE
        assert isinstance(image._original_size, tuple)
        assert image._original_size == python_img.size

        image = BlockImage(python_img, width=None)
        assert image._size is Size.FIT
        image = BlockImage(python_img, height=None)
        assert image._size is Size.FIT
        image = BlockImage(python_img, width=None, height=None)
        assert image._size is Size.FIT

        image = BlockImage(python_img, width=_size)
        assert isinstance(image._size, tuple)
        image = BlockImage(python_img, height=_size)
        assert isinstance(image._size, tuple)

        for value in Size:
            image = BlockImage(python_img, width=value)
            assert isinstance(image._size, tuple)
            image = BlockImage(python_img, height=value)
            assert isinstance(image._size, tuple)

        image = BlockImage(python_img, scale=(0.5, 0.4))
        assert image._scale == [0.5, 0.4]

        assert image._is_animated is False

    def test_init_animated(self):
        image = BlockImage(anim_img)
        assert image._is_animated is True
        assert image._frame_duration == (anim_img.info.get("duration") or 100) / 1000
        assert image._seek_position == 0
        assert image._n_frames is None

        try:
            anim_img.seek(2)
            assert BlockImage(anim_img)._seek_position == 2
        finally:
            anim_img.seek(0)


class TestFromFile:
    def test_args(self):
        with pytest.raises(TypeError, match=r"a string"):
            BlockImage.from_file(python_img)
        with pytest.raises(FileNotFoundError):
            BlockImage.from_file(python_image + "e")
        with pytest.raises(IsADirectoryError):
            BlockImage.from_file("tests")
        with pytest.raises(UnidentifiedImageError):
            BlockImage.from_file("LICENSE")

        # Ensure size arguments get through
        with pytest.raises(ValueError, match=r"both width and height"):
            BlockImage.from_file(python_image, width=1, height=1)

        # Ensure scale argument gets through
        with pytest.raises(TypeError, match=r"'scale'"):
            BlockImage.from_file(python_image, scale=1.0)

    def test_filepath(self):
        image = BlockImage.from_file(python_image)
        assert isinstance(image, BlockImage)
        assert image._source == os.path.abspath(python_image)
        assert image._source_type is ImageSource.FILE_PATH

    @pytest.mark.skipif(
        not os.path.islink(python_sym),
        reason="The symlink is on or has passed through a platform or filesystem that "
        "doesn't support symlinks",
    )
    def test_symlink(self):
        image = BlockImage.from_file(python_sym)
        assert isinstance(image, BlockImage)
        assert image._source == os.path.abspath(python_sym)
        assert image._source_type is ImageSource.FILE_PATH


class TestProperties:
    def test_closed(self):
        image = BlockImage(python_img)
        assert not image.closed

        with pytest.raises(AttributeError):
            image.closed = True

        image.close()
        assert image.closed

    def test_frame_duration(self):
        image = BlockImage(python_img)
        assert image.frame_duration is None
        image.frame_duration = 0.5
        assert image.frame_duration is None

        image = BlockImage(anim_img)
        assert image._frame_duration == (anim_img.info.get("duration") or 100) / 1000

        for duration in (0, 1, "0.1", "1", 0.3j):
            with pytest.raises(TypeError):
                image.frame_duration = duration
        for duration in (0.0, -0.1):
            with pytest.raises(ValueError):
                image.frame_duration = duration

        image.frame_duration = 0.5
        assert image.frame_duration == 0.5

    def test_height(self):
        image = BlockImage(python_img)
        assert image.height is Size.FIT

        image.height = _size
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        assert image.size[1] == _size == image.height

        for value in Size:
            image.height = value
            assert isinstance(image.size, tuple)
            assert isinstance(image.width, int)
            assert isinstance(image.height, int)

        image.height = None
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        size = image.size
        image.height = Size.FIT
        assert image.size == size

        for value in (0.1, "1", (1, 1), [1, 1]):
            with pytest.raises(TypeError):
                image.height = value
        for value in (-1, 0):
            with pytest.raises(ValueError):
                image.height = value

    def test_is_animated(self):
        image = BlockImage(python_img)
        assert not image.is_animated

        image = BlockImage(anim_img)
        assert image.is_animated

        with pytest.raises(AttributeError):
            image.is_animated = False

    def test_n_frames(self):
        image = BlockImage(python_img)
        assert image.n_frames == 1

        image = BlockImage(anim_img)
        assert 1 < image.n_frames == anim_img.n_frames
        assert image.n_frames == anim_img.n_frames  # Ensure consistency

        with pytest.raises(AttributeError):
            image.n_frames = 2

    def test_original_size(self):
        image = BlockImage(python_img)

        for value in (None, 0, 1, 0.1, "1", (1, 1), [1, 1]):
            with pytest.raises(AttributeError):
                image.original_size = value

        assert image.original_size == python_img.size
        assert isinstance(image.original_size, tuple)

    def test_rendered_size_height_width(self):
        image = BlockImage(python_img)  # Square

        with pytest.raises(AttributeError):
            image.rendered_size = (_size,) * 2
        with pytest.raises(AttributeError):
            image.rendered_height = _size
        with pytest.raises(AttributeError):
            image.rendered_width = _size

        assert isinstance(image.rendered_size, tuple)
        assert isinstance(image.rendered_width, int)
        assert isinstance(image.rendered_height, int)

        image.width = _width

        assert isinstance(image.rendered_size, tuple)
        assert isinstance(image.rendered_width, int)
        assert isinstance(image.rendered_height, int)

        # Varying scales
        for value in range(1, 101):
            scale = value / 100
            image.scale = scale
            assert image.rendered_width == round(_width * scale)
            assert image.rendered_height == round(_height * scale)

        # Random scales
        for _ in range(100):
            scale = random()
            if scale == 0:
                continue
            image.scale = scale
            assert image.rendered_width == round(_width * scale)
            assert image.rendered_height == round(_height * scale)

        image.scale = 1.0

        # The rendered size is independent of the font ratio
        # Change in font-ratio must not affect the image's rendered size
        try:
            set_font_ratio(0.5)
            image.width = _width
            assert image.rendered_size == (_width, _height)
            set_font_ratio(0.1)
            assert image.rendered_size == (_width, _height)
        finally:
            set_font_ratio(0.5)

    def test_scale_value_checks(self):
        image = BlockImage(python_img)

        # Value type
        for value in (0, 1, None, "1", "1.0"):
            with pytest.raises(TypeError):
                image.scale = value
        for value in (0, 1, None, "1", "1.0", (1.0, 1.0)):
            with pytest.raises(TypeError):
                image.scale_x = value
            with pytest.raises(TypeError):
                image.scale_y = value

        # Value range
        for value in (0.0, -0.1, 1.0001, 2.0):
            with pytest.raises(ValueError):
                image.scale = value
            with pytest.raises(ValueError):
                image.scale_x = value
            with pytest.raises(ValueError):
                image.scale_y = value

        # Tuple item type
        for value in ((1, 1), (1.0, 1), (1, 1.0), ("1.0",)):
            with pytest.raises(TypeError):
                image.scale = value

        # Tuple length
        for value in ((0.5,), (0.5,) * 3):
            with pytest.raises(ValueError):
                image.scale = value

        # Tuple item value range
        for value in (
            (0.0, 0.5),
            (0.5, 0.0),
            (-0.5, 0.5),
            (0.5, -0.5),
            (1.1, 0.5),
            (0.5, 1.1),
        ):
            with pytest.raises(ValueError):
                image.scale = value

    def test_scale_x_y(self):
        image = BlockImage(python_img)
        assert image.scale == (1.0, 1.0)
        assert image.scale_x == image.scale_y == 1.0

        assert isinstance(image.scale, tuple)
        assert isinstance(image.scale_x, float)
        assert isinstance(image.scale_y, float)

        image.scale = 0.5
        assert image.scale == (0.5,) * 2
        assert image.scale_x == image.scale_y == 0.5

        image.scale_x = 0.25
        assert image.scale_x == image.scale[0] == 0.25
        assert image.scale_y == 0.5

        image.scale_y = 0.75
        assert image.scale_y == image.scale[1] == 0.75
        assert image.scale_x == 0.25

    def test_size(self):
        image = BlockImage(python_img)
        assert image.size is Size.FIT

        for value in Size:
            image.size = value
            assert image.size is image.height is image.width is value

        for value in (None, 0, 1, 0.1, "1", (1, 1), [1, 1]):
            with pytest.raises(TypeError):
                image.size = value

    def test_source(self):
        image = BlockImage(python_img)
        assert image.source is python_img
        assert image.source_type is ImageSource.PIL_IMAGE

        image = BlockImage.from_file(python_image)
        assert image.source == os.path.abspath(python_image)
        assert image.source_type is ImageSource.FILE_PATH

        with pytest.raises(AttributeError):
            image.source = None

    @pytest.mark.skipif(
        not os.path.islink(python_sym),
        reason="The symlink is on or has passed through a platform or filesystem that "
        "doesn't support symlinks",
    )
    def test_source_symlink(self):
        image = BlockImage.from_file(python_sym)
        assert os.path.basename(image.source) == "python_sym.png"
        assert (
            image.source == os.path.abspath(python_sym) != os.path.realpath(python_sym)
        )
        assert image.source_type is ImageSource.FILE_PATH

    def test_width(self):
        image = BlockImage(python_img)
        assert image.width is Size.FIT

        image.width = _size
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        assert image.size[0] == _size == image.width

        for value in Size:
            image.width = value
            assert isinstance(image.size, tuple)
            assert isinstance(image.width, int)
            assert isinstance(image.height, int)

        image.width = None
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        size = image.size
        image.width = Size.FIT
        assert image.size == size

        for value in (0.1, "1", (1, 1), [1, 1]):
            with pytest.raises(TypeError):
                image.width = value
        for value in (-1, 0):
            with pytest.raises(ValueError):
                image.width = value


def test_close():
    image = BlockImage(python_img)
    image.close()
    assert image.closed
    with pytest.raises(AttributeError):
        image._source
    with pytest.raises(TermImageError):
        image.source
    with pytest.raises(TermImageError):
        str(image)
    with pytest.raises(TermImageError):
        format(image)
    with pytest.raises(TermImageError):
        image.draw()


def test_context_management():
    image = BlockImage(python_img)
    with image as image2:
        assert image2 is image
    assert image.closed


def test_iter():
    image = BlockImage(python_img)
    with pytest.raises(ValueError, match="not animated"):
        iter(image)

    anim_image = BlockImage(anim_img)
    image_it = iter(anim_image)
    assert isinstance(image_it, ImageIterator)
    assert image_it._image is anim_image


def test_seek_tell():
    # Non-animated
    image = BlockImage(python_img)
    assert image.tell() == 0
    image.seek(0)
    assert image.tell() == 0
    with pytest.raises(ValueError, match="out of range"):
        image.seek(1)
    assert image.tell() == 0

    # Animated
    image = BlockImage(anim_img)
    assert image.tell() == 0
    n_frames = anim_img.n_frames

    image.seek(2)
    assert image.tell() == 2

    with pytest.raises(ValueError, match="out of range"):
        image.seek(n_frames)
    assert image.tell() == 2

    image.seek(n_frames - 1)
    assert image.tell() == n_frames - 1

    with pytest.raises(ValueError, match="out of range"):
        image.seek(n_frames + 1)
    assert image.tell() == n_frames - 1

    image.seek(0)
    assert image.tell() == 0


class TestSetSize:
    image = BlockImage(python_img)  # Square
    h_image = BlockImage.from_file("tests/images/hori.jpg")  # Horizontally-oriented
    v_image = BlockImage.from_file("tests/images/vert.jpg")  # Vertically-oriented

    def test_args_width_height(self):
        for value in (1, *Size):
            with pytest.raises(ValueError, match=".* both width and height"):
                self.image.set_size(value, value)
        for value in (1.0, "1", (), []):
            with pytest.raises(TypeError, match="'width' must be"):
                self.image.set_size(value)
            with pytest.raises(TypeError, match="'height' must be"):
                self.image.set_size(height=value)
        for value in (0, -1, -100):
            with pytest.raises(ValueError, match="'width' must be"):
                self.image.set_size(value)
            with pytest.raises(ValueError, match="'height' must be"):
                self.image.set_size(height=value)

    def test_args_allow(self):
        for value in (1.0, "1", (), []):
            with pytest.raises(TypeError, match="'h_allow' must be"):
                self.image.set_size(h_allow=value)
            with pytest.raises(TypeError, match="'v_allow' must be"):
                self.image.set_size(v_allow=value)
        for value in (-1, -100):
            with pytest.raises(ValueError, match="'h_allow' must be"):
                self.image.set_size(h_allow=value)
            with pytest.raises(ValueError, match="'v_allow' must be"):
                self.image.set_size(v_allow=value)

    def test_args_maxsize(self):
        for value in (1, 1.0, "1", (1.0, 1), (1, 1.0), ("1.0",)):
            with pytest.raises(TypeError, match="'maxsize' must be"):
                self.image.set_size(maxsize=value)
        for value in ((), (0,), (1,), (1, 1, 1), (0, 1), (1, 0), (-1, 1), (1, -1)):
            with pytest.raises(ValueError, match="'maxsize' must contain"):
                self.image.set_size(maxsize=value)

    def test_cannot_exceed_maxsize(self):
        with pytest.raises(InvalidSizeError, match="will not fit into"):
            self.image.set_size(width=101, maxsize=(100, 50))  # Exceeds on both axes
        with pytest.raises(InvalidSizeError, match="will not fit into"):
            self.image.set_size(width=101, maxsize=(100, 100))  # Exceeds horizontally
        with pytest.raises(InvalidSizeError, match="will not fit into"):
            self.image.set_size(height=51, maxsize=(200, 50))  # Exceeds Vertically

        # Horizontal image in a (supposedly) square space; Exceeds horizontally
        with pytest.raises(InvalidSizeError, match="will not fit into"):
            self.h_image.set_size(height=100, maxsize=(100, 50))

        # Vertical image in a (supposedly) square space; Exceeds Vertically
        with pytest.raises(InvalidSizeError, match="will not fit into"):
            self.v_image.set_size(width=100, maxsize=(100, 50))


def test_renderer():
    def test(img, *args, **kwargs):
        return img, args, kwargs

    image = BlockImage(python_img)

    for positionals, keywords in (
        ((), {}),
        ((2,), {"d": "dude"}),
        ((1, 2, 3), {"a": 1, "b": 2, "c": 3}),
    ):
        img, args, kwargs = image._renderer(test, *positionals, **keywords)
        assert isinstance(img, Image.Image)
        assert args == positionals
        assert kwargs == keywords


class TestRenderData:
    # Fully transparent image
    # It's easy to predict it's pixel values
    trans = BlockImage.from_file("tests/images/trans.png")
    trans.height = _size
    trans.scale = 1.0

    def get_render_data(self, img=None, alpha=None, **kwargs):
        return self.trans._get_render_data(
            img or self.trans._get_image(), alpha, **kwargs
        )

    def test_small_size_scale(self):
        try:
            for self.trans._size in ((1, 0), (0, 1), (0, 0)):
                with pytest.raises(ValueError, match="too small"):
                    self.get_render_data(None)
        finally:
            self.trans.height = _size

        try:
            self.trans.scale = 0.0001
            with pytest.raises(ValueError, match="too small"):
                self.get_render_data(None)
        finally:
            self.trans.scale = 1.0

    def test_alpha(self):

        # float
        for alpha in (0.0, _ALPHA_THRESHOLD, 0.999):
            img, _, a = self.get_render_data(alpha=alpha)
            assert isinstance(img, Image.Image)
            assert img.mode == "RGBA"
            assert all(px == 0 for px in a)

            rgb_img = self.trans._get_image().convert("RGB")
            img, _, a = self.get_render_data(rgb_img, alpha)
            assert isinstance(img, Image.Image)
            assert img.mode == "RGB"
            assert all(px == 255 for px in a)

        # str
        for alpha in ("#ffffff", "#"):
            img, _, a = self.get_render_data(alpha=alpha)
            assert isinstance(img, Image.Image)
            assert img.mode == "RGB"
            assert all(px == 255 for px in a)

            rgb_img = self.trans._get_image().convert("RGB")
            img, _, a = self.get_render_data(rgb_img, alpha)
            assert isinstance(img, Image.Image)
            assert img.mode == "RGB"
            assert all(px == 255 for px in a)

        # None
        img, _, a = self.get_render_data(alpha=None)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert all(px == 255 for px in a)

        rgb_img = self.trans._get_image().convert("RGB")
        img, _, a = self.get_render_data(rgb_img, None)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert all(px == 255 for px in a)

    def test_size(self):
        for alpha in (_ALPHA_THRESHOLD, "#", None):
            render_size = self.trans._get_render_size()
            img, rgb, a = self.get_render_data(alpha=alpha)
            assert isinstance(img, Image.Image)
            assert img.size == render_size
            assert len(rgb) == len(a) == mul(*render_size)

            size = (47, 31)
            img, rgb, a = self.get_render_data(alpha=alpha, size=size)
            assert isinstance(img, Image.Image)
            assert img.size == size
            assert len(rgb) == len(a) == mul(*size)

    def test_pixel_data(self):
        for alpha in (_ALPHA_THRESHOLD, "#", None):
            img, rgb, a = self.get_render_data(alpha=alpha)
            assert isinstance(img, Image.Image)
            assert isinstance(rgb, list)
            assert isinstance(a, list)

            img, rgb, a = self.get_render_data(alpha=alpha, pixel_data=False)
            assert isinstance(img, Image.Image)
            assert rgb is None
            assert rgb is None

    def test_round_alpha(self):
        image = BlockImage(python_img, height=_size)
        img, rgb, a = image._get_render_data(python_img, alpha=_ALPHA_THRESHOLD)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        assert any(px not in {0, 255} for px in a)

        img, rounded_rgb, a = image._get_render_data(
            python_img, alpha=_ALPHA_THRESHOLD, round_alpha=True
        )
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        assert all(px in {0, 255} for px in a)

        assert rgb != rounded_rgb  # Blends rounded rgb with terminal BG


# As long as each subclass passes it's render tests (particulary those related to the
# size of the render results), then testing formatting with a single style should
# suffice.
class TestFormatting:
    image = BlockImage(python_img)
    image.scale = 0.5  # To ensure there's padding
    render = str(image)
    check_formatting = staticmethod(image._check_formatting)
    format_render = image._format_render

    def test_args(self):
        self.image.set_size()
        for value in (1, 1.0, (), []):
            with pytest.raises(TypeError, match="'h_align' must be .*"):
                self.check_formatting(h_align=value)
            with pytest.raises(TypeError, match="'v_align' must be .*"):
                self.check_formatting(v_align=value)

        for value in ("", "cool", ".", " ", "\n"):
            with pytest.raises(ValueError, match="Invalid horizontal .*"):
                self.check_formatting(h_align=value)
            with pytest.raises(ValueError, match="Invalid vertical .*"):
                self.check_formatting(v_align=value)

        for value in ("1", 1.0, (), []):
            with pytest.raises(TypeError, match="Padding width must be .*"):
                self.check_formatting(width=value)
            with pytest.raises(TypeError, match="Padding height must be .*"):
                self.check_formatting(height=value)

        for value in (0, -1, -100):
            with pytest.raises(ValueError, match="Padding width must be .*"):
                self.check_formatting(width=value)
            with pytest.raises(ValueError, match="Padding height must be .*"):
                self.check_formatting(height=value)

    def test_arg_align_conversion(self):
        self.image.set_size()
        assert self.check_formatting() == (None,) * 4

        for value in "<|>":
            assert self.check_formatting(h_align=value) == (value, None, None, None)
        for val1, val2 in zip(("left", "center", "right"), "<|>"):
            assert self.check_formatting(h_align=val1) == (val2, None, None, None)

        for value in "^-_":
            assert self.check_formatting(v_align=value) == (None, None, value, None)
        for val1, val2 in zip(("top", "middle", "bottom"), "^-_"):
            assert self.check_formatting(v_align=val1) == (None, None, val2, None)

    def test_arg_padding_width(self):
        self.image.set_size()
        for value in (1, _width, columns):
            assert self.check_formatting(width=value) == (None, value, None, None)

        # Can exceed terminal width
        assert self.check_formatting(width=columns + 1) == (
            None,
            columns + 1,
            None,
            None,
        )

        # Allowance is not considered
        self.image.set_size(h_allow=2)
        assert self.check_formatting(width=columns) == (None, columns, None, None)

    def test_arg_padding_height(self):
        self.image.set_size()
        for value in (1, _size, lines):
            assert self.check_formatting(height=value) == (None, None, None, value)

        # Can exceed terminal height
        assert self.check_formatting(height=lines + 1) == (None, None, None, lines + 1)

        # Allowance is not considered
        self.image.set_size(v_allow=4)
        assert self.check_formatting(height=lines) == (None, None, None, lines)

    def test_padding_width(self):
        self.image.set_size()
        for width in range(self.image.rendered_width, columns + 1):
            assert (
                self.format_render(self.render, "<", width)
                .partition("\n")[0]
                .count(" ")
                == width
            )
            assert (
                self.format_render(self.render, "|", width)
                .partition("\n")[0]
                .count(" ")
                == width
            )
            assert (
                self.format_render(self.render, ">", width)
                .partition("\n")[0]
                .count(" ")
                == width
            )
            assert (
                self.format_render(self.render, None, width)
                .partition("\n")[0]
                .count(" ")
                == width
            )

    def test_padding_height(self):
        self.image.set_size()
        for height in range(self.image.rendered_height, lines + 1):
            assert (
                self.format_render(self.render, None, None, "^", height).count("\n") + 1
                == height
            )
            assert (
                self.format_render(self.render, None, None, "-", height).count("\n") + 1
                == height
            )
            assert (
                self.format_render(self.render, None, None, "_", height).count("\n") + 1
                == height
            )
            assert (
                self.format_render(self.render, None, None, None, height).count("\n")
                + 1
                == height
            )

    def test_align_left_top(self):
        self.image.set_size()
        render = self.format_render(self.render, "<", columns, "^", lines)
        assert (
            len(render.partition("\n")[0].rpartition("m")[2])
            == columns - self.image.rendered_width
        )
        assert (
            render.rpartition("m")[2].count("\n") == lines - self.image.rendered_height
        )

    def test_align_center_middle(self):
        self.image.set_size()
        render = self.format_render(self.render, "|", columns, "-", lines)
        left = (columns - self.image.rendered_width) // 2
        right = columns - self.image.rendered_width - left
        up = (lines - self.image.rendered_height) // 2
        down = lines - self.image.rendered_height - up

        partition = render.rpartition("m")[0]
        assert partition.rpartition("\n")[2].index(ESC) == left
        assert render.partition(ESC)[0].count("\n") == up

        partition = render.partition(ESC)[2]
        assert len(partition.partition("\n")[0].rpartition("m")[2]) == right
        assert render.rpartition("m")[2].count("\n") == down

    def test_align_right_bottom(self):
        self.image.set_size()
        render = self.format_render(self.render, ">", columns, "_", lines)
        assert (
            render.rpartition("\n")[2].index(ESC) == columns - self.image.rendered_width
        )
        assert (
            render.partition(ESC)[0].count("\n") == lines - self.image.rendered_height
        )

    # First line in every render should be padding (except the terminal is so small)
    # No '\n' after the last line, hence the `+ 1` when counting lines

    def test_allowance_default(self):
        self.image.set_size()
        render = self.format_render(self.render)
        assert render.partition("\n")[0].count(" ") == columns
        assert render.count("\n") + 1 == lines - 2

    def test_allowance_non_default(self):
        self.image.set_size(h_allow=2, v_allow=3)
        render = self.format_render(str(self.image))
        assert render.partition("\n")[0].count(" ") == columns - 2
        assert render.count("\n") + 1 == lines - 3

    def test_allowance_fit_to_width(self):
        # Vertical allowance nullified
        self.image.set_size(Size.FIT_TO_WIDTH, h_allow=2, v_allow=3)
        render = self.format_render(str(self.image))
        assert render.partition("\n")[0].count(" ") == columns - 2
        assert render.count("\n") + 1 == lines

    def test_allowance_maxsize(self):
        # `maxsize` ignores but doesn't nullify allowances
        self.image.set_size(h_allow=2, v_allow=3, maxsize=(_size,) * 2)
        render = self.format_render(str(self.image))
        assert render.partition("\n")[0].count(" ") == columns - 2
        assert render.count("\n") + 1 == lines - 3

    def test_format_spec(self):
        for spec in (
            "1<",
            "-1.|1",
            "<1.1^",
            ".",
            "1.",
            "<.",
            ">1.",
            "-",
            "<^",
            ".#",
            ">1.#.23",
            "#0",
            "#.",
            "#2445",
            "#.23fa45",
            "#fffffff",
            "#a45gh4",
            "###",
            " ",
            # style-specific section
            "+",
            "20+",
            ".^+",
            "#+",
        ):
            with pytest.raises(ValueError, match=r"Invalid format specifier"):
                self.image._check_format_spec(spec)

        for spec in (
            "<",
            "1",
            ".1",
            "<1",
            ".^1",
            "|1.-1",
            "<1.-",
            ".-",
            "#",
            "##",
            "#123456",
            "#23af5b",
            "#abcdef",
            "#.4",
            "#.343545453453",
            "1.1#",
            "1.1##",
            "<.^#ffffff",
            "<1.^1#.2",
            f"<{columns}.^{lines}##",
        ):
            fmt = self.image._check_format_spec(spec)
            assert isinstance(fmt, tuple)


# Testing with one style should suffice for all since it's simply testing the method
# and nothing perculiar to the style
class TestDraw:
    image = BlockImage(python_img, width=_size)
    anim_image = BlockImage(anim_img, width=_size)

    def test_args(self):
        sys.stdout = stdout
        for value in (1, (), [], {}, b""):
            with pytest.raises(TypeError, match="'alpha' must be"):
                self.image.draw(alpha=value)

        for value in (-1.0, -0.1, 1.0, 1.1):
            with pytest.raises(ValueError, match="Alpha threshold"):
                self.image.draw(alpha=value)

        for value in ("f", "fffff", "fffffff", "12h45g", "-2343"):
            with pytest.raises(ValueError, match="Invalid hex color"):
                self.image.draw(alpha=value)

        with pytest.raises(ValueError, match="Padding width"):
            self.image.draw(pad_width=columns + 1)

        self.image.set_size(h_allow=2)
        with pytest.raises(ValueError, match="Padding width"):
            self.image.draw(pad_width=columns - 1)

        with pytest.raises(ValueError, match="Padding height"):
            self.anim_image.draw(pad_height=lines + 1)

        for value in (1, 1.0, "1", (), []):
            with pytest.raises(TypeError, match="'animate' .* boolean"):
                self.anim_image.draw(animate=value)

        for arg in ("scroll", "check_size"):
            for value in (1, 1.0, "1", (), []):
                with pytest.raises(TypeError, match=f"{arg!r} .* boolean"):
                    self.image.draw(**{arg: value})

    def test_size_validation(self):
        sys.stdout = stdout
        self.image._size = (columns + 1, 1)
        with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
            self.image.draw()

        self.image._size = (1, lines - 1)
        with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
            self.image.draw()

        self.image.set_size(h_allow=2)
        self.image._size = (columns - 1, 1)
        with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
            self.image.draw()

        self.image.set_size(v_allow=4)
        self.image._size = (1, lines - 3)
        with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
            self.image.draw()

    class TestNonAnimated:
        image = BlockImage(python_img, width=_size)
        anim_image = BlockImage(anim_img, width=_size)

        def test_fit_to_width(self):
            sys.stdout = stdout
            self.image.set_size(Size.FIT_TO_WIDTH)
            self.image._size = (columns, lines + 1)
            self.image.draw()
            assert stdout.getvalue().count("\n") == lines + 1
            clear_stdout()

        def test_scroll(self):
            sys.stdout = stdout
            self.image.set_size()
            self.image._size = (columns, lines + 1)
            self.image.draw(scroll=True)
            assert stdout.getvalue().count("\n") == lines + 1
            clear_stdout()

        def test_check_size(self):
            sys.stdout = stdout
            self.image.set_size()
            self.image._size = (columns + 1, lines)
            self.image.draw(check_size=False)
            assert stdout.getvalue().count("\n") == lines
            clear_stdout()

    class TestAnimatedFalse:
        image = BlockImage(python_img, width=_size)
        anim_image = BlockImage(anim_img, width=_size)

        def test_fit_to_width(self):
            sys.stdout = stdout
            self.anim_image.set_size(Size.FIT_TO_WIDTH)
            self.anim_image._size = (columns, lines + 1)
            self.anim_image.draw(animate=False)
            assert stdout.getvalue().count("\n") == lines + 1
            clear_stdout()

        def test_scroll(self):
            sys.stdout = stdout
            self.anim_image.set_size()
            self.anim_image._size = (columns, lines + 1)
            self.anim_image.draw(scroll=True, animate=False)
            assert stdout.getvalue().count("\n") == lines + 1
            clear_stdout()

        def test_check_size(self):
            sys.stdout = stdout
            self.anim_image.set_size()
            self.anim_image._size = (columns + 1, lines)
            self.anim_image.draw(animate=False, check_size=False)
            assert stdout.getvalue().count("\n") == lines
            clear_stdout()

    class TestAnimated:
        image = BlockImage(python_img)
        anim_image = BlockImage(anim_img)

        def test_fit_to_width(self):
            sys.stdout = stdout
            self.anim_image.set_size(Size.FIT_TO_WIDTH)
            self.anim_image._size = (columns, lines + 1)
            with pytest.raises(InvalidSizeError, match="rendered height .* animations"):
                self.anim_image.draw()

        def test_scroll(self):
            sys.stdout = stdout
            self.anim_image.set_size()
            self.anim_image._size = (columns, lines + 1)
            with pytest.raises(InvalidSizeError, match="rendered height .* animations"):
                self.anim_image.draw(scroll=True)

        def test_fit_scroll(self):
            sys.stdout = stdout
            self.anim_image.set_size(Size.FIT_TO_WIDTH)
            self.anim_image._size = (columns, lines + 1)
            with pytest.raises(InvalidSizeError, match="rendered height .* animations"):
                self.anim_image.draw(scroll=True)

        def test_check_size(self):
            sys.stdout = stdout
            self.anim_image.set_size()
            self.anim_image._size = (columns + 1, lines)
            with pytest.raises(
                InvalidSizeError, match="animation cannot .* terminal size"
            ):
                self.anim_image.draw(check_size=False)

        def test_fit_scroll_check_size(self):
            sys.stdout = stdout
            self.anim_image.set_size(Size.FIT_TO_WIDTH)
            self.anim_image._size = (columns + 1, lines + 1)
            with pytest.raises(
                InvalidSizeError, match="animation cannot .* terminal size"
            ):
                self.anim_image.draw(scroll=True, check_size=False)
