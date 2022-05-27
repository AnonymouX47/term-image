"""Render-style-dependent (though shared, not specific) tests"""

from operator import gt, lt
from types import SimpleNamespace

import pytest
from PIL import Image

from term_image import set_font_ratio
from term_image.exceptions import TermImageException
from term_image.image.common import _ALPHA_THRESHOLD, GraphicsImage, TextImage
from term_image.utils import get_terminal_size

from . import set_cell_size

columns, lines = get_terminal_size()

# For square images
dummy = SimpleNamespace()
dummy._original_size = (1, 1)
_width = _height = _width_px = _height_px = None  # Set by `setup()`

_size = 20
ImageClass = None  # Set by `setup()`
python_img = Image.open("tests/images/python.png")


def setup_common(ImageClass):
    globals().update(locals())  # width_height() requires ImageClass

    set_cell_size((9, 18))
    set_font_ratio(0.5)

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
        with pytest.raises(TermImageException):
            ImageClass(python_img)
    finally:
        ImageClass._supported = original


def test_str_All():
    image = ImageClass(python_img, width=_size)
    assert str(image) == image._render_image(python_img, _ALPHA_THRESHOLD)


def test_format_All():
    image = ImageClass(python_img)
    image.set_size()
    image.scale = 0.5  # Leave some space for formatting
    assert format(image) == image._format_render(str(image))


def test_is_supported_All():
    assert isinstance(ImageClass.is_supported(), bool)


def test_set_render_method_All():
    for value in (2, 2.0, ()):
        with pytest.raises(TypeError):
            ImageClass.set_render_method(value)

    assert ImageClass.set_render_method() is True
    assert ImageClass.set_render_method("") is False

    image = ImageClass(python_img)
    assert image.set_render_method() is True
    assert image.set_render_method(None) is True
    assert image.set_render_method("") is False


# Size-setting is taken as style-dependent because the major underlying API is
# style-specific
class TestSetSize_All:
    def test_setup(self):
        type(self).image = ImageClass(python_img)  # Square
        # Horizontally-oriented
        type(self).h_image = ImageClass.from_file("tests/images/hori.jpg")
        # Vertically-oriented
        type(self).v_image = ImageClass.from_file("tests/images/vert.jpg")

    def test_auto_sizing_and_proportionality(self):
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

    def test_width_and_proportionality(self):
        self.image.set_size(width=_size)
        assert self.image.width == _size
        assert proportional(self.image)

        self.h_image.set_size(width=_size)
        assert self.image.width == _size
        assert proportional(self.image)

        self.v_image.set_size(width=_size)
        assert self.image.width == _size
        assert proportional(self.image)

    def test_height_and_proportionality(self):
        self.image.set_size(height=_size)
        assert self.image.height == _size
        assert proportional(self.image)

        self.h_image.set_size(height=_size)
        assert self.image.height == _size
        assert proportional(self.image)

        self.v_image.set_size(height=_size)
        assert self.image.height == _size
        assert proportional(self.image)

    def test_fitted_axes_and_proportionality(self):
        self.h_image.set_size(fit_to_height=True)
        assert self.h_image.height == lines - 2
        assert proportional(self.image)

        self.v_image.set_size(fit_to_width=True)
        assert self.v_image.width == columns
        assert proportional(self.image)

    def test_allowance(self):
        self.image.set_size(fit_to_width=True)
        assert self.image.width == columns

        self.image.set_size(fit_to_height=True)
        assert self.image.height == lines - 2

        self.image.set_size(h_allow=2, fit_to_width=True)
        assert self.image.width == columns - 2

        self.image.set_size(v_allow=3, fit_to_height=True)
        assert self.image.height == lines - 3

    def test_can_exceed_terminal_size(self):
        self.image.set_size(width=columns + 1)
        assert self.image.width == columns + 1
        assert proportional(self.image)

        self.image.set_size(height=lines + 1)
        assert self.image.height == lines + 1
        assert proportional(self.image)


# Specific to text-based render styles because the results are dependent on font ratio.
# These tests only pass when the font ratio is about 0.5.
class TestSetSize_Text:
    def test_setup(self):
        type(self).image = ImageClass(python_img)  # Square

    def test_maxsize(self):
        self.image.set_size(maxsize=(100, 50))
        assert self.image.size == (100, 50)
        self.image.set_size(maxsize=(100, 55))
        assert self.image.size == (100, 50)
        self.image.set_size(maxsize=(110, 50))
        assert self.image.size == (100, 50)

        self.image.set_size(width=100, maxsize=(200, 100))
        assert self.image.size == (100, 50)
        self.image.set_size(height=50, maxsize=(200, 100))
        assert self.image.size == (100, 50)

    def test_maxsize_allowance_nullification(self):
        self.image.set_size(h_allow=2, v_allow=3, maxsize=(100, 50))
        assert self.image.size == (100, 50)
        self.image.set_size(h_allow=2, v_allow=3, maxsize=(100, 50))
        assert self.image.size == (100, 50)


class TestFontRatio_Text:
    def test_setup(self):
        type(self).image = ImageClass(python_img)  # Square

    def test_fixed_width_font_ratio_adjustment(self):
        try:
            for ratio in (0.01, 0.1, 0.25, 0.4, 0.45, 0.55, 0.6, 0.75, 0.9, 0.99, 1.0):
                set_font_ratio(ratio)
                self.image.set_size(width=_size)
                assert self.image.width == _size
                assert proportional(self.image)
        finally:
            set_font_ratio(0.5)

    def test_fixed_height_font_ratio_adjustment(self):
        try:
            for ratio in (0.01, 0.1, 0.25, 0.4, 0.45, 0.55, 0.6, 0.75, 0.9, 0.99, 1.0):
                set_font_ratio(ratio)
                self.image.set_size(height=_size)
                assert self.image.height == _size
                assert proportional(self.image)
        finally:
            set_font_ratio(0.5)

    def test_auto_size_font_ratio_adjustment(self):
        try:
            for ratio in (0.01, 0.1, 0.25, 0.4, 0.45, 0.55, 0.6, 0.75, 0.9, 0.99, 1.0):
                set_font_ratio(ratio)
                self.image.set_size()
                assert proportional(self.image)
        finally:
            set_font_ratio(0.5)


class TestFontRatio_Graphics:
    def test_setup(self):
        type(self).image = ImageClass(python_img)  # Square

    def test_font_ratio_adjustment(self):
        self.image.set_size()
        size = self.image.size
        try:
            for ratio in (0.01, 0.1, 0.25, 0.4, 0.45, 0.55, 0.6, 0.75, 0.9, 0.99, 1.0):
                set_font_ratio(ratio)
                self.image.set_size()
                assert self.image.size == size
        finally:
            set_font_ratio(0.5)


__all__ = [name for name in globals() if name.startswith(("test_", "Test"))]
