"""Render-style-dependent (though shared, not specific) tests"""

import atexit
from operator import gt, lt, mul
from types import SimpleNamespace

import pytest
from PIL import Image

from term_image import set_cell_ratio
from term_image._ctlseqs import SGR_BG_DIRECT, SGR_DEFAULT
from term_image.exceptions import StyleError
from term_image.image.common import _ALPHA_THRESHOLD, GraphicsImage, Size, TextImage
from term_image.utils import get_fg_bg_colors, get_terminal_size

from .. import (
    reset_cell_size_ratio,
    set_cell_size,
    set_fg_bg_colors,
    toggle_is_on_kitty,
)

columns, lines = get_terminal_size()

# For square images
dummy = SimpleNamespace()
dummy._original_size = (1, 1)
_width = _height = _width_px = _height_px = None  # Set by `setup_common()`

_size = 20
ImageClass = None  # Set by `setup_common()`
python_img = Image.open("tests/images/python.png")


@atexit.register
def close_imgs():
    python_img.close()


def setup_common(ImageClass):
    globals().update(locals())  # width_height() requires ImageClass

    set_cell_size((9, 18))
    set_cell_ratio(0.5)

    if ImageClass._pixels_cols(cols=columns) < ImageClass._pixels_lines(
        lines=lines - 2
    ):
        _width = columns
        _height = width_height(dummy, w=columns)
    else:
        _height = lines - 2
        _width = width_height(dummy, h=lines - 2)
    _width_px = ImageClass._pixels_cols(cols=_width)
    _height_px = ImageClass._pixels_lines(lines=_height)

    globals().update(locals())


def proportional(image):
    ori_width, ori_height = image.original_size
    # The converted width and height in pixels might not be exactly proportional
    # as they have been previously rounded to meet cell boundaries but the
    # difference must be less than the number of pixels for one line
    if _width_px < _height_px:
        # Height was adjusted
        return (
            abs(
                image._pixels_cols(cols=image.width) / ori_width
                # Was adjusted by multiplying, so we divide
                - (image._pixels_lines(lines=image.height) / image._pixel_ratio)
                / ori_height
            )
            < image._pixels_lines(lines=1) / ori_height
        )
    else:
        # Width was adjusted
        return (
            abs(
                # Was adjusted by dividing, so we multiply
                (image._pixels_cols(cols=image.width) * image._pixel_ratio) / ori_width
                - image._pixels_lines(lines=image.height) / ori_height
            )
            < image._pixels_lines(lines=1) / ori_height
        )


def width_height(image, *, w=None, h=None):
    return (
        ImageClass._pixels_lines(
            pixels=round(
                ImageClass._width_height_px(
                    image,
                    w=ImageClass._pixels_cols(cols=w),
                )
            )
        )
        if w is not None
        else ImageClass._pixels_cols(
            pixels=round(
                ImageClass._width_height_px(
                    image,
                    h=ImageClass._pixels_lines(lines=h),
                )
            )
        )
    )


def get_actual_render_size(image):
    render_size = image._get_render_size()

    if image._render_method != "whole":
        return render_size

    _, r_height = image.rendered_size
    width, height = (
        render_size
        if mul(*render_size) < mul(*image._original_size)
        else image._original_size
    )
    if image._render_method != "whole":
        extra = height % (r_height or 1)
        if extra:
            height = height - extra + r_height

    return width, height


def test_instantiation_Text():
    original = ImageClass._supported
    try:
        ImageClass._supported = True
        assert isinstance(ImageClass(python_img), TextImage)
        ImageClass._supported = False
        assert isinstance(ImageClass(python_img), TextImage)
    finally:
        ImageClass._supported = original


def test_instantiation_Graphics():
    original = ImageClass._supported
    try:
        ImageClass._supported = True
        assert isinstance(ImageClass(python_img), GraphicsImage)
        ImageClass._supported = False
        with pytest.raises(StyleError):
            ImageClass(python_img)
    finally:
        ImageClass._supported = original


def test_str_All():
    image = ImageClass(python_img, width=_size)
    assert str(image) == image._render_image(python_img, _ALPHA_THRESHOLD)


def test_format_All():
    image = ImageClass(python_img)
    image.set_size()
    image.width //= 2  # To ensure there's padding
    assert format(image) == image._format_render(str(image), *image._check_formatting())


def test_is_supported_All():
    assert isinstance(ImageClass.is_supported(), bool)


def test_forced_support_Graphics():
    original = ImageClass._supported
    try:
        ImageClass._supported = False
        with pytest.raises(StyleError):
            ImageClass(python_img)

        ImageClass.forced_support = True
        assert isinstance(ImageClass(python_img), GraphicsImage)

        ImageClass.forced_support = False
        with pytest.raises(StyleError):
            ImageClass(python_img)
    finally:
        ImageClass._supported = original


def test_set_render_method_All():
    for value in (2, 2.0, ()):
        with pytest.raises(TypeError):
            ImageClass.set_render_method(value)

    default = ImageClass._default_render_method if ImageClass._render_methods else None

    with pytest.raises(ValueError):
        ImageClass.set_render_method("")

    assert ImageClass._render_method == default
    assert ImageClass.set_render_method() is None
    for method in ImageClass._render_methods:
        assert ImageClass.set_render_method(method) is None

    assert ImageClass.set_render_method(None) is None
    assert ImageClass._render_method == default
    if default is None:
        assert "_render_method" not in vars(ImageClass)

    image = ImageClass(python_img)

    with pytest.raises(ValueError):
        image.set_render_method("")

    assert image._render_method == default
    assert image.set_render_method() is None
    for method in image._render_methods:
        assert image.set_render_method(method) is None

    assert image.set_render_method(None) is None
    assert image._render_method == default
    if default is None:
        assert "_render_method" not in vars(image)


# Size-setting is taken as style-dependent because the major underlying interface is
# style-specific
class TestSetSize_All:
    def test_setup(self):
        type(self).image = ImageClass(python_img)  # Square
        # Horizontally-oriented
        type(self).h_image = ImageClass.from_file("tests/images/hori.jpg")
        # Vertically-oriented
        type(self).v_image = ImageClass.from_file("tests/images/vert.jpg")

    def test_auto(self):
        frame_width_px = ImageClass._pixels_cols(cols=columns)
        frame_height_px = ImageClass._pixels_lines(lines=lines - 2)

        _original_size = self.image.original_size
        try:
            # Equal to frame size
            self.image._original_size = (frame_width_px, frame_height_px)
            self.image.set_size(Size.AUTO)
            assert self.image._valid_size(Size.ORIGINAL) == self.image.size

            # Horizontally larger than frame size
            self.image._original_size = (frame_width_px + 20, frame_height_px - 20)
            self.image.set_size(Size.AUTO)
            assert (
                self.image._valid_size(Size.ORIGINAL)
                != self.image.size
                == self.image._valid_size(Size.FIT)
            )

            # Vertically larger than frame size
            self.image._original_size = (frame_width_px - 20, frame_height_px + 20)
            self.image.set_size(Size.AUTO)
            assert (
                self.image._valid_size(Size.ORIGINAL)
                != self.image.size
                == self.image._valid_size(Size.FIT)
            )

            # Horizontally and vertically larger than frame size
            self.image._original_size = (frame_width_px + 20, frame_height_px + 20)
            self.image.set_size(Size.AUTO)
            assert (
                self.image._valid_size(Size.ORIGINAL)
                != self.image.size
                == self.image._valid_size(Size.FIT)
            )

            # Smaller than frame size
            self.image._original_size = (frame_width_px - 20, frame_height_px - 20)
            self.image.set_size(Size.AUTO)
            assert (
                self.image._valid_size(Size.ORIGINAL)
                == self.image.size
                != self.image._valid_size(Size.FIT)
            )
        finally:
            self.image._original_size = _original_size

    def test_fit_none_default(self):
        self.image.set_size()
        size = self.image.size

        self.image.set_size(width=Size.FIT)
        assert self.image.size == size

        self.image.set_size(height=Size.FIT)
        assert self.image.size == size

        self.image.set_size(width=None)
        assert self.image.size == size

        self.image.set_size(height=None)
        assert self.image.size == size

    # a PASS is valid only if the previous test passed
    def test_fit(self):
        self.image.set_size()
        assert self.image.size == (_width, _height) == self.image._size
        assert proportional(self.image)

        self.h_image.set_size()
        assert gt(
            self.h_image._pixels_cols(cols=self.h_image.width),
            self.h_image._pixels_lines(lines=self.h_image.height),
        )
        assert proportional(self.h_image)

        self.v_image.set_size()
        assert lt(
            self.v_image._pixels_cols(cols=self.v_image.width),
            self.v_image._pixels_lines(lines=self.v_image.height),
        )
        assert proportional(self.v_image)

    def test_fit_to_width_width(self):
        self.image.set_size(width=Size.FIT_TO_WIDTH)
        assert self.image.width == columns
        assert proportional(self.image)

        self.h_image.set_size(width=Size.FIT_TO_WIDTH)
        assert self.h_image.width == columns
        assert proportional(self.h_image)

        self.v_image.set_size(width=Size.FIT_TO_WIDTH)
        assert self.v_image.width == columns
        assert proportional(self.v_image)

    def test_fit_to_width_height(self):
        self.image.set_size(height=Size.FIT_TO_WIDTH)
        assert self.image.width == columns
        assert proportional(self.image)

        self.h_image.set_size(height=Size.FIT_TO_WIDTH)
        assert self.h_image.width == columns
        assert proportional(self.h_image)

        self.v_image.set_size(height=Size.FIT_TO_WIDTH)
        assert self.v_image.width == columns
        assert proportional(self.v_image)

    def test_int_width(self):
        self.image.set_size(width=_size)
        assert self.image.width == _size
        assert proportional(self.image)

        self.h_image.set_size(width=_size)
        assert self.h_image.width == _size
        assert proportional(self.h_image)

        self.v_image.set_size(width=_size)
        assert self.v_image.width == _size
        assert proportional(self.v_image)

    def test_int_height(self):
        self.image.set_size(height=_size)
        assert self.image.height == _size
        assert proportional(self.image)

        self.h_image.set_size(height=_size)
        assert self.h_image.height == _size
        assert proportional(self.h_image)

        self.v_image.set_size(height=_size)
        assert self.v_image.height == _size
        assert proportional(self.v_image)

    def test_original_width(self):
        ori_width, ori_height = self.image.original_size
        self.image.set_size(width=Size.ORIGINAL)
        assert self.image.width == ImageClass._pixels_cols(pixels=ori_width)
        assert proportional(self.image)

        ori_width, ori_height = self.h_image.original_size
        self.h_image.set_size(width=Size.ORIGINAL)
        assert self.h_image.width == ImageClass._pixels_cols(pixels=ori_width)
        assert proportional(self.h_image)

        ori_width, ori_height = self.v_image.original_size
        self.v_image.set_size(width=Size.ORIGINAL)
        assert self.v_image.width == ImageClass._pixels_cols(pixels=ori_width)
        assert proportional(self.v_image)

    def test_original_height(self):
        ori_width, ori_height = self.image.original_size
        self.image.set_size(height=Size.ORIGINAL)
        assert self.image.height == ImageClass._pixels_lines(pixels=ori_height)
        assert proportional(self.image)

        ori_width, ori_height = self.h_image.original_size
        self.h_image.set_size(height=Size.ORIGINAL)
        assert self.h_image.height == ImageClass._pixels_lines(pixels=ori_height)
        assert proportional(self.h_image)

        ori_width, ori_height = self.v_image.original_size
        self.v_image.set_size(height=Size.ORIGINAL)
        assert self.v_image.height == ImageClass._pixels_lines(pixels=ori_height)
        assert proportional(self.v_image)

    def test_can_exceed_terminal_size(self):
        self.image.set_size(width=columns + 1)
        assert self.image.width == columns + 1
        assert proportional(self.image)

        self.image.set_size(height=lines + 1)
        assert self.image.height == lines + 1
        assert proportional(self.image)


class TestCellRatio_Text:
    def test_setup(self):
        type(self).image = ImageClass(python_img)  # Square

    @reset_cell_size_ratio()
    def test_fixed_width_cell_ratio_adjustment(self):
        for ratio in (0.01, 0.1, 0.25, 0.4, 0.45, 0.55, 0.6, 0.75, 0.9, 0.99, 1.0):
            set_cell_ratio(ratio)
            self.image.set_size(width=_size)
            assert self.image.width == _size
            assert proportional(self.image)

    @reset_cell_size_ratio()
    def test_fixed_height_cell_ratio_adjustment(self):
        for ratio in (0.01, 0.1, 0.25, 0.4, 0.45, 0.55, 0.6, 0.75, 0.9, 0.99, 1.0):
            set_cell_ratio(ratio)
            self.image.set_size(height=_size)
            assert self.image.height == _size
            assert proportional(self.image)

    @reset_cell_size_ratio()
    def test_auto_size_cell_ratio_adjustment(self):
        for ratio in (0.01, 0.1, 0.25, 0.4, 0.45, 0.55, 0.6, 0.75, 0.9, 0.99, 1.0):
            set_cell_ratio(ratio)
            self.image.set_size()
            assert proportional(self.image)


class TestCellRatio_Graphics:
    def test_setup(self):
        type(self).image = ImageClass(python_img)  # Square

    @reset_cell_size_ratio()
    def test_cell_ratio_adjustment(self):
        self.image.set_size()
        size = self.image.size
        for ratio in (0.01, 0.1, 0.25, 0.4, 0.45, 0.55, 0.6, 0.75, 0.9, 0.99, 1.0):
            set_cell_ratio(ratio)
            self.image.set_size()
            assert self.image.size == size


class TestRender_Text:
    def test_setup(self):
        type(self).trans = ImageClass.from_file("tests/images/trans.png", height=_size)

    def render_image(self, alpha, *, split_cells=False):
        return self.trans._renderer(
            self.trans._render_image, alpha, split_cells=split_cells
        )

    def test_is_on_kitty(self):
        for bg, r in (((0,) * 3, 1), ((100,) * 3, 101), ((255,) * 3, 254), (None, 0)):
            set_fg_bg_colors(bg=bg)
            bg_hex = get_fg_bg_colors(hex=True)[1]
            bg = bg or (0, 0, 0)

            assert all(
                line == SGR_BG_DIRECT % bg + " " * self.trans.width + SGR_DEFAULT
                for line in self.render_image("#").splitlines()
            )
            assert all(
                line == SGR_BG_DIRECT % bg + " " * self.trans.width + SGR_DEFAULT
                for line in self.render_image(bg_hex).splitlines()
            )

            toggle_is_on_kitty()
            bg = (r, *bg[1:])

            assert all(
                line == SGR_BG_DIRECT % bg + " " * self.trans.width + SGR_DEFAULT
                for line in self.render_image("#").splitlines()
            )
            assert all(
                line == SGR_BG_DIRECT % bg + " " * self.trans.width + SGR_DEFAULT
                for line in self.render_image(bg_hex).splitlines()
            )

            toggle_is_on_kitty()
        set_fg_bg_colors((0, 0, 0), (0, 0, 0))

    def test_split_cells(self):
        render_no_split = self.render_image(_ALPHA_THRESHOLD, split_cells=False)
        render_split = self.render_image(_ALPHA_THRESHOLD, split_cells=True)

        assert render_no_split == str(self.trans)
        assert render_split != render_no_split
        assert render_split.replace("\0", "") == render_no_split
        assert render_split.count("\n") == render_no_split.count("\n")

        for split_line, no_split_line in zip(
            render_split.splitlines(), render_no_split.splitlines()
        ):
            cells = split_line.strip(SGR_DEFAULT).split("\0")

            assert "".join(split_line.split("\0")) == no_split_line
            assert len(cells) == _size
            for cell in cells:
                assert cell == " "

        python_image = ImageClass(python_img, width=_size)
        render = python_image._renderer(
            python_image._render_image, _ALPHA_THRESHOLD, split_cells=True
        )

        for line, str_line in zip(render.splitlines(), str(python_image).splitlines()):
            cells = line.split("\0")
            assert len(cells) == _size
            assert "".join(cells) == str_line


def test_render_clean_up_All():
    # PIL_IMAGE
    img = Image.open("tests/images/python.png")
    img_copy = img.copy()
    image = ImageClass(img)
    # Source
    image._render_image(img, None)
    img.load()
    # Frame
    image._render_image(img_copy, None, frame=True)
    img_copy.load()
    # Not source and not frame
    image._render_image(img_copy, None)
    with pytest.raises(ValueError, match="closed"):
        img_copy.load()

    # FILE, also applies for URL
    image = ImageClass.from_file("tests/images/python.png")
    img = image._get_image()
    # Frame
    image._render_image(img, None, frame=True)
    img.load()
    # Not source and not frame
    image._render_image(img, None)
    with pytest.raises(ValueError, match="closed"):
        img.load()


def test_style_args_All():
    image = ImageClass(python_img)
    with pytest.raises(StyleError):
        image.draw(_=None)


def test_style_format_spec_All():
    image = ImageClass(python_img)
    for spec in ("+\t", "20+\r", ".^+\a", "#+\0"):
        with pytest.raises(StyleError):
            format(image, spec)


__all__ = [name for name in globals() if name.startswith(("test_", "Test"))]
