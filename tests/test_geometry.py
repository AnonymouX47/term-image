import pytest

from term_image.geometry import RawSize, Size


class TestRawSize:
    @pytest.mark.parametrize("width", [1, 0, -1])
    def test_width(self, width):
        size = RawSize(width, 1)
        assert size.width == width

    @pytest.mark.parametrize("height", [1, 0, -1])
    def test_height(self, height):
        size = RawSize(1, height)
        assert size.height == height

    def test_is_tuple(self):
        size = RawSize(1, -1)
        assert isinstance(size, tuple)
        assert len(size) == 2
        assert size == (1, -1)
        assert size[0] == 1
        assert size[1] == -1

    class TestNew:
        def test_instance_type(self):
            class SubRawSize(RawSize):
                pass

            assert type(RawSize._new(1, 1)) is RawSize
            assert type(SubRawSize._new(1, 1)) is SubRawSize

        @pytest.mark.parametrize("size", [(1, 10), (0, 1), (0, 0), (-1, 0), (-10, -1)])
        def test_equal_to_normally_constructed(self, size):
            assert RawSize._new(*size) == RawSize(*size)


class TestSize:
    @pytest.mark.parametrize("value", [0, -1])
    def test_positive_dimensions_only(self, value):
        with pytest.raises(ValueError, match="'width'"):
            Size(value, 1)
        with pytest.raises(ValueError, match="'height'"):
            Size(1, value)

    def test_width(self):
        assert Size(10, 1).width == 10

    def test_height(self):
        assert Size(1, 10).height == 10

    def test_is_tuple(self):
        size = Size(1, 10)
        assert isinstance(size, tuple)
        assert len(size) == 2
        assert size == (1, 10)
        assert size[0] == 1
        assert size[1] == 10
