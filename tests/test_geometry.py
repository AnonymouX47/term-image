import pytest

from term_image.geometry import Size


class TestSize:
    def test_args(self):
        with pytest.raises(TypeError, match="'width'"):
            Size(2.0, 1)
        with pytest.raises(TypeError, match="'height'"):
            Size(1, 2.0)

    def test_tuple(self):
        size = Size(1, 1)
        assert isinstance(size, tuple)
        assert len(size) == 2

    def test_width(self):
        size = Size(1, -1)
        assert size[0] == 1 == size.width

    def test_height(self):
        size = Size(1, -1)
        assert size[1] == -1 == size.height
