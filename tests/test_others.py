from operator import truediv
from random import randint, random

import pytest

from term_image import FontRatio, get_font_ratio, set_font_ratio
from term_image.exceptions import TermImageError
from term_image.image import AutoImage, BaseImage, ImageSource, from_file

from . import set_cell_size
from .test_base import python_image, python_img


class TestConvinience:
    def test_auto_image(self):
        with pytest.raises(TypeError, match=r"'PIL\.Image\.Image' instance"):
            AutoImage(python_image)

        # Ensure size arguments get through
        with pytest.raises(ValueError, match=r"both width and height"):
            AutoImage(python_img, width=1, height=1)

        # Ensure scale argument gets through
        with pytest.raises(TypeError, match=r"'scale'"):
            AutoImage(python_img, scale=0.5)

        assert isinstance(AutoImage(python_img), BaseImage)

    def test_from_file(self):
        with pytest.raises(TypeError, match=r"a string"):
            from_file(python_img)

        # Ensure size arguments get through
        with pytest.raises(ValueError, match=r"both width and height"):
            from_file(python_image, width=1, height=1)

        # Ensure scale argument gets through
        with pytest.raises(TypeError, match=r"'scale'"):
            from_file(python_image, scale=1.0)

        assert isinstance(from_file(python_image), BaseImage)


class TestFontRatio:
    def test_args(self):
        for value in (0, "1", ()):
            with pytest.raises(TypeError, match=r"'ratio' must be"):
                set_font_ratio(value)
        for value in (0.0, -0.1, -1.0):
            with pytest.raises(ValueError, match=r"'ratio' must be"):
                set_font_ratio(value)

        set_cell_size(None)
        for value in FontRatio:
            with pytest.raises(TermImageError):
                set_font_ratio(value)

    def test_fixed(self):
        for value in (0.01, 0.1, 0.9, 0.99, 1.0, 2.0):
            set_font_ratio(value)
            assert get_font_ratio() == value

        for _ in range(20):
            value = random()
            set_font_ratio(value)
            assert get_font_ratio() == value

    def test_auto(self):
        set_cell_size((4, 9))
        set_font_ratio(FontRatio.AUTO)
        assert get_font_ratio() == 4 / 9 == get_font_ratio()

        for _ in range(20):
            cell_size = (randint(1, 20), randint(1, 20))
            set_cell_size(cell_size)
            set_font_ratio(FontRatio.AUTO)
            assert get_font_ratio() == truediv(*cell_size) == get_font_ratio()
            set_cell_size((0, 1))
            assert get_font_ratio() == truediv(*cell_size)

    def test_full_auto(self):
        set_cell_size((4, 9))
        set_font_ratio(FontRatio.FULL_AUTO)
        assert get_font_ratio() == 4 / 9 == get_font_ratio()

        for _ in range(20):
            cell_size = (randint(1, 20), randint(1, 20))
            set_cell_size(cell_size)
            assert get_font_ratio() == truediv(*cell_size) == get_font_ratio()


def test_image_source():
    assert len(ImageSource) == 3
    assert all(member.name == name for name, member in ImageSource.__members__.items())
