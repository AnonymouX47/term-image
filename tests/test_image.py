import os
from math import ceil
from operator import gt, lt
from shutil import get_terminal_size

import pytest
from PIL import Image, UnidentifiedImageError

from term_img import set_font_ratio
from term_img.exceptions import InvalidSize
from term_img.image import TermImage

columns, lines = term_size = get_terminal_size()
rows = lines * 2
_size = min(columns, rows - 4)

python_image = "tests/images/python.png"
python_img = Image.open(python_image)
anim_img = Image.open("tests/images/anim.webp")


class TestInstantiation:
    def test_constructor(self):
        with pytest.raises(TypeError, match=r".* 'PIL\.Image\.Image' instance .*"):
            TermImage(python_image)

        image = TermImage(python_img)
        assert image._size is None
        assert isinstance(image._scale, list)
        assert image._scale == [1.0, 1.0]
        assert image._source is python_img
        assert isinstance(image._original_size, tuple)
        assert image._original_size == python_img.size
        assert image._is_animated is False

        image = TermImage(anim_img)
        assert image._is_animated is True
        assert image._frame_duration == 0.1
        assert image._seek_position == 0
        assert image._n_frames == image.n_frames

        # Ensure size arguments get through to `set_size()`
        with pytest.raises(ValueError, match=r".* both width and height"):
            TermImage(python_img, width=1, height=1)
        image = TermImage(python_img, width=_size)
        assert isinstance(image._size, tuple)
        image = TermImage(python_img, height=_size)
        assert isinstance(image._size, tuple)

        with pytest.raises(TypeError, match=r"'scale' .*"):
            image = TermImage(python_img, scale=0.5)

        for value in ((0.0, 0.0), (-0.4, -0.4)):
            with pytest.raises(ValueError, match=r"'scale' .*"):
                image = TermImage(python_img, scale=value)

        image = TermImage(python_img, scale=(0.5, 0.4))
        assert isinstance(image._scale, list)
        assert image._scale == [0.5, 0.4]

    def test_from_file(self):
        with pytest.raises(TypeError, match=r".* a string .*"):
            TermImage.from_file(python_img)
        with pytest.raises(FileNotFoundError):
            TermImage.from_file(python_image + "e")
        with pytest.raises(IsADirectoryError):
            TermImage.from_file("tests")
        with pytest.raises(UnidentifiedImageError):
            TermImage.from_file("LICENSE")

        image = TermImage.from_file(python_image)
        assert isinstance(image, TermImage)
        assert image._source == os.path.realpath(python_image)

        # Ensure size arguments get through
        with pytest.raises(ValueError, match=r".* both width and height"):
            TermImage.from_file(python_image, width=1, height=1)

        # Ensure scale argument gets through
        with pytest.raises(TypeError, match=r"'scale' .*"):
            TermImage.from_file(python_image, scale=1.0)


def test_format_spec():
    image = TermImage(python_img)

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
        " ",
    ):
        with pytest.raises(ValueError, match=r"Invalid format specifier"):
            format(image, spec)

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
        "#123456",
        "#23af5b",
        "#abcdef",
        "#.4",
        "#.343545453453",
        "1.1#",
        "<.^#ffffff",
    ):
        assert isinstance(format(image, spec), str)


class TestProperties:
    def test_closed(self):
        image = TermImage(python_img)
        assert not image.closed

        with pytest.raises(AttributeError):
            image.closed = True

        image.close()
        assert image.closed

    def test_frame_duration(self):
        image = TermImage(python_img)
        assert image.frame_duration is None
        image.frame_duration = 0.5
        assert image.frame_duration is None

        image = TermImage(anim_img)
        assert image.frame_duration == 0.1

        for duration in (0, 1, "0.1", "1", 0.3j):
            with pytest.raises(TypeError):
                image.frame_duration = duration
        for duration in (0.0, -0.1):
            with pytest.raises(ValueError):
                image.frame_duration = duration

        image.frame_duration = 0.5
        assert image.frame_duration == 0.5

    def test_is_animated(self):
        image = TermImage(python_img)
        assert not image.is_animated

        image = TermImage(anim_img)
        assert image.is_animated

        with pytest.raises(AttributeError):
            image.is_animated = False

    def test_n_frames(self):
        image = TermImage(python_img)
        assert image.n_frames == 1

        image = TermImage(anim_img)
        assert image.n_frames > 1

        with pytest.raises(AttributeError):
            image.n_frames = 0

    def test_rendered_size_height_width(self):
        image = TermImage(python_img)

        with pytest.raises(AttributeError):
            image.rendered_size = 0
        with pytest.raises(AttributeError):
            image.rendered_height = 0
        with pytest.raises(AttributeError):
            image.rendered_width = 0

        assert isinstance(image.rendered_size, tuple)
        assert isinstance(image.rendered_width, int)
        assert isinstance(image.rendered_height, int)

        # The test image is square
        assert image.rendered_width == _size
        assert image.rendered_height == ceil(_size / 2)
        assert image.rendered_size == (_size, ceil(_size / 2))

        set_font_ratio(0.75)
        assert image.rendered_width < _size
        assert image.rendered_height == ceil(_size / 2)
        set_font_ratio(0.5)  # Reset

    def test_scale_x_y(self):
        image = TermImage(python_img)
        assert image.scale == (1.0, 1.0)
        assert image.scale_x == image.scale_y == 1.0

        assert isinstance(image.scale, tuple)
        assert isinstance(image.scale_x, float)
        assert isinstance(image.scale_y, float)

        for value in (0, 1, None, "1", "1.0"):
            with pytest.raises(TypeError):
                image.scale = value
            with pytest.raises(TypeError):
                image.scale_x = value
            with pytest.raises(TypeError):
                image.scale_y = value

        for value in (0.0, -0.1, 1.0001, 2.0):
            with pytest.raises(ValueError):
                image.scale = value
            with pytest.raises(ValueError):
                image.scale_x = value
            with pytest.raises(ValueError):
                image.scale_y = value

        for value in ((1, 1), (1.0, 1), (1, 1.0), ("1.0",)):
            with pytest.raises(TypeError):
                image.scale = value

        for value in (
            (0.5,),
            (0.5,) * 3,
            (0.0, 0.5),
            (0.5, 0.0),
            (-0.5, 0.5),
            (0.5, -0.5),
            (1.1, 0.5),
            (0.5, 1.1),
        ):
            with pytest.raises(ValueError):
                image.scale = value

        image.scale = 0.5
        assert image.scale == (0.5,) * 2
        assert image.scale_x == image.scale_y == 0.5

        image.scale_x = 0.25
        assert image.scale_x == image.scale[0] == 0.25
        assert image.scale_y == 0.5

        image.scale_y = 0.75
        assert image.scale_y == image.scale[1] == 0.75
        assert image.scale_x == 0.25

    def test_size_height_width(self):
        image = TermImage(python_img)
        assert image.original_size == python_img.size
        assert image.size is image.height is image.width is None

        image.width = _size
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        assert image.size[0] == _size == image.width

        image.height = 1
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        assert image.size[1] == 1 == image.height

        for size in (0, 1, 0.1, "1", (1, 1), [1, 1]):
            with pytest.raises(TypeError):
                image.size = size
        image.size = None
        assert image.size is image.height is image.width is None

    def test_source(self):
        image = TermImage(python_img)
        assert image.source is python_img

        image = TermImage.from_file(python_image)
        assert image.source == os.path.realpath(python_image)

        with pytest.raises(AttributeError):
            image.source = None


def test_set_size():
    image = TermImage(python_img)
    h_image = TermImage.from_file("tests/images/hori.jpg")
    v_image = TermImage.from_file("tests/images/vert.jpg")

    # Default args
    image.set_size()
    assert image._size == (_size,) * 2
    h_image.set_size()
    assert gt(*h_image._size)
    v_image.set_size()
    assert lt(*v_image._size)

    # width and height
    with pytest.raises(ValueError, match=".* both width and height"):
        image.set_size(1, 1)
    for value in (1.0, "1", (), []):
        with pytest.raises(TypeError, match="'width' must be .*"):
            image.set_size(value)
        with pytest.raises(TypeError, match="'height' must be .*"):
            image.set_size(height=value)
    for value in (0, -1, -100):
        with pytest.raises(ValueError, match="'width' must be .*"):
            image.set_size(value)
        with pytest.raises(ValueError, match="'height' must be .*"):
            image.set_size(height=value)

    # h_allow and v_allow
    for value in (1.0, "1", (), []):
        with pytest.raises(TypeError, match="'h_allow' must be .*"):
            image.set_size(h_allow=value)
        with pytest.raises(TypeError, match="'v_allow' must be .*"):
            image.set_size(v_allow=value)
    for value in (-1, -100):
        with pytest.raises(ValueError, match="'h_allow' must be .*"):
            image.set_size(h_allow=value)
        with pytest.raises(ValueError, match="'v_allow' must be .*"):
            image.set_size(v_allow=value)

    # maxsize
    for value in (1, 1.0, "1", (1.0, 1), (1, 1.0), ("1.0",)):
        with pytest.raises(TypeError, match="'maxsize' must be .*"):
            image.set_size(maxsize=value)
    for value in ((), (0,), (1,), (1, 1, 1), (0, 1), (1, 0), (-1, 1), (1, -1)):
        with pytest.raises(ValueError, match="'maxsize' must contain .*"):
            image.set_size(maxsize=value)

    # check_width and check_height
    for value in (1, 1.0, "1", (), []):
        with pytest.raises(TypeError, match=".* booleans"):
            image.set_size(check_width=value)
        with pytest.raises(TypeError, match=".* booleans"):
            image.set_size(check_height=value)

    # Size computation errors
    with pytest.raises(InvalidSize, match=".* too small: .*"):
        h_image.set_size(width=1)
    with pytest.raises(InvalidSize, match=".* too small: .*"):
        v_image.set_size(height=1)
    with pytest.raises(InvalidSize, match=".* will not fit into .*"):
        image.set_size(_size + 1)

    # Controlling the size by the axis with a larger fraction, will cause the image not
    # to fit on the other axis

    ori_width, ori_height = h_image._original_size
    with pytest.raises(InvalidSize, match=".* will not fit into .*"):
        if columns / ori_width > (rows - 4) / ori_height:
            h_image.set_size(width=columns)
        else:
            h_image.set_size(height=rows - 4)

    ori_width, ori_height = v_image._original_size
    with pytest.raises(InvalidSize, match=".* will not fit into .*"):
        if columns / ori_width > (rows - 4) / ori_height:
            v_image.set_size(width=columns)
        else:
            v_image.set_size(height=rows - 4)

    # Proportionality
    image.set_size(width=_size)
    assert image._size == (_size,) * 2
    image.set_size(height=_size)
    assert image._size == (_size,) * 2

    h_image.set_size(width=_size)
    ori_width, ori_height = h_image._original_size
    assert h_image._size == (_size, round(ori_height * _size / ori_width))

    v_image.set_size(height=_size)
    ori_width, ori_height = v_image._original_size
    assert v_image._size == (round(ori_width * _size / ori_height), _size)

    # Proportionality with oversized axes
    h_image.set_size(check_width=False)
    ori_width, ori_height = h_image._original_size
    assert h_image._size[0] == round(ori_width * (rows - 4) / ori_height)

    v_image.set_size(check_height=False)
    ori_width, ori_height = v_image._original_size
    assert v_image._size[1] == round(ori_height * columns / ori_width)

    image.set_size(max(columns + 1, rows), check_width=False, check_height=False)
    assert image._size == (max(columns + 1, rows),) * 2

    # Allowance
    image.set_size(check_height=False)
    assert image._size[0] == columns

    image.set_size(check_width=False)
    assert image._size[0] == rows - 4

    image.set_size(h_allow=2, check_height=False)
    assert image._size[0] == columns - 2

    image.set_size(v_allow=3, check_width=False)
    assert image._size[0] == rows - 6

    # Maxsize (+ allowance nullification)
    image.set_size(h_allow=2, v_allow=3, maxsize=(100, 55))
    assert image._size == (100, 100)  # Square image
    image.set_size(h_allow=2, v_allow=3, maxsize=(110, 50))
    assert image._size == (100, 100)  # Square image
