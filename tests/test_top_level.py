from operator import truediv
from random import randint, random

import pytest

from term_image import AutoCellRatio, get_cell_ratio, set_cell_ratio
from term_image.exceptions import TermImageError

from . import reset_cell_size_ratio, set_cell_size


class TestCellRatio:
    @reset_cell_size_ratio()
    def test_args(self):
        for value in (0, "1", ()):
            with pytest.raises(TypeError, match=r"'ratio' must be"):
                set_cell_ratio(value)
        for value in (0.0, -0.1, -1.0):
            with pytest.raises(ValueError, match=r"'ratio' must be"):
                set_cell_ratio(value)

        set_cell_size(None)
        for value in AutoCellRatio:
            with pytest.raises(TermImageError):
                set_cell_ratio(value)

    @reset_cell_size_ratio()
    def test_fixed(self):
        for value in (0.01, 0.1, 0.9, 0.99, 1.0, 2.0):
            set_cell_ratio(value)
            assert get_cell_ratio() == value

        for _ in range(20):
            value = random()
            set_cell_ratio(value)
            assert get_cell_ratio() == value

    @reset_cell_size_ratio()
    def test_fixed_auto(self):
        set_cell_size((4, 9))
        set_cell_ratio(AutoCellRatio.FIXED)
        assert get_cell_ratio() == 4 / 9 == get_cell_ratio()

        for _ in range(20):
            cell_size = (randint(1, 20), randint(1, 20))
            set_cell_size(cell_size)
            set_cell_ratio(AutoCellRatio.FIXED)
            assert get_cell_ratio() == truediv(*cell_size) == get_cell_ratio()
            set_cell_size((0, 1))
            assert get_cell_ratio() == truediv(*cell_size)

    @reset_cell_size_ratio()
    def test_dynamic_auto(self):
        set_cell_size((4, 9))
        set_cell_ratio(AutoCellRatio.DYNAMIC)
        assert get_cell_ratio() == 4 / 9 == get_cell_ratio()

        for _ in range(20):
            cell_size = (randint(1, 20), randint(1, 20))
            set_cell_size(cell_size)
            assert get_cell_ratio() == truediv(*cell_size) == get_cell_ratio()
