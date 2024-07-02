from operator import truediv

import pytest

from term_image import (
    AutoCellRatio,
    disable_queries,
    disable_win_size_swap,
    enable_queries,
    enable_win_size_swap,
    get_cell_ratio,
    set_cell_ratio,
    set_query_timeout,
    utils,
)
from term_image.exceptions import TermImageError
from term_image.geometry import Size

from . import reset_cell_size_ratio, set_cell_size


class TestCellRatio:
    class TestManual:
        @pytest.mark.parametrize("ratio", [0.0, -0.1, -1.0])
        @reset_cell_size_ratio()
        def test_invalid(self, ratio):
            with pytest.raises(ValueError):
                set_cell_ratio(ratio)

        @pytest.mark.parametrize("ratio", [0.01, 0.5, 0.99, 1.0, 2.0])
        @reset_cell_size_ratio()
        def test_valid(self, ratio):
            set_cell_ratio(ratio)
            assert get_cell_ratio() == ratio

    class TestAuto:
        @pytest.mark.parametrize("auto_mode", AutoCellRatio)
        @reset_cell_size_ratio()
        def test_unsupported(self, auto_mode):
            set_cell_size(None)
            with pytest.raises(TermImageError):
                set_cell_ratio(auto_mode)

        @pytest.mark.parametrize("cell_size", [Size(4, 9), Size(11, 20)])
        @reset_cell_size_ratio()
        def test_fixed(self, cell_size):
            set_cell_size(cell_size)
            set_cell_ratio(AutoCellRatio.FIXED)
            assert get_cell_ratio() == truediv(*cell_size)

            # Same after cell size changes
            set_cell_size(Size(1, 1))
            assert get_cell_ratio() == truediv(*cell_size)

        @reset_cell_size_ratio()
        def test_dynamic(self):
            set_cell_size(Size(4, 9))
            set_cell_ratio(AutoCellRatio.DYNAMIC)
            assert get_cell_ratio() == 4 / 9 == get_cell_ratio()

            # Changes along with cell size
            set_cell_size(Size(11, 20))
            assert get_cell_ratio() == 11 / 20 == get_cell_ratio()

            # Use 0.5 when cell size can't be determined
            set_cell_size(None)
            assert get_cell_ratio() == 1 / 2 == get_cell_ratio()

            # Back to normal when cell size can be determined
            set_cell_size(Size(5, 5))
            assert get_cell_ratio() == 5 / 5 == get_cell_ratio()


def test_disable_queries():
    utils._queries_enabled = True

    disable_queries()
    assert not utils._queries_enabled


@pytest.mark.parametrize("was_enabled", [True, False])
def test_disable_win_size_swap(was_enabled):
    utils._swap_win_size = was_enabled
    utils._cell_size_cache[:] = (1, 2, 3, 4)

    disable_win_size_swap()
    assert not utils._swap_win_size
    assert utils._cell_size_cache == [0, 0, 0, 0] if was_enabled else [1, 2, 3, 4]


@pytest.mark.parametrize("was_enabled", [True, False])
def test_enable_queries(was_enabled):
    utils._queries_enabled = was_enabled
    utils._cell_size_cache[:] = (1, 2, 3, 4)

    enable_queries()
    assert utils._queries_enabled
    assert utils._cell_size_cache == [1, 2, 3, 4] if was_enabled else [0, 0, 0, 0]


@pytest.mark.parametrize("was_enabled", [True, False])
def test_enable_win_size_swap(was_enabled):
    utils._swap_win_size = was_enabled
    utils._cell_size_cache[:] = (1, 2, 3, 4)

    enable_win_size_swap()
    assert utils._swap_win_size
    assert utils._cell_size_cache == [1, 2, 3, 4] if was_enabled else [0, 0, 0, 0]


class TestSetQueryTimeout:
    @pytest.mark.parametrize("timeout", [-1.0, -0.1, 0.0])
    def test_invalid(self, timeout):
        with pytest.raises(ValueError):
            set_query_timeout(timeout)

    @pytest.mark.parametrize("timeout", [0.1, 0.5, 1.0, 10.0])
    def test_valid(self, timeout):
        set_query_timeout(timeout)
        assert utils._query_timeout == timeout
