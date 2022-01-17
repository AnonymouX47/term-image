import os
from math import ceil
from shutil import get_terminal_size

import pytest
from PIL import Image, UnidentifiedImageError

from term_img import set_font_ratio
from term_img.exceptions import URLNotFoundError
from term_img.image import TermImage

columns, lines = term_size = get_terminal_size()
rows = lines * 2
_size = min(columns, rows - 4)

python_image = "tests/images/python.png"
python_url = (
    "https://raw.githubusercontent.com/AnonymouX47/term-img/main/tests/"
    "images/python.png"
)
python_img = Image.open(python_image)

anim_image = "tests/images/anim.webp"
anim_url = (
    "https://raw.githubusercontent.com/AnonymouX47/term-img/main/tests/"
    "images/anim.webp"
)
anim_img = Image.open(anim_image)


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

        with pytest.raises(ValueError, match=r".* both width and height"):
            TermImage(python_img, width=1, height=1)

        image = TermImage(python_img, width=_size)
        assert isinstance(image._original_size, tuple)
        assert image._size == (_size,) * 2

        image = TermImage(python_img, height=_size)
        assert isinstance(image._original_size, tuple)
        assert image._size == (_size,) * 2

        with pytest.raises(TypeError, match=r"'scale' .*"):
            image = TermImage(python_img, scale=0.5)

        with pytest.raises(ValueError, match=r"'scale' .*"):
            image = TermImage(python_img, scale=(0.0, 0.0))

        with pytest.raises(ValueError, match=r"'scale' .*"):
            image = TermImage(python_img, scale=(-0.4, -0.4))

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

    def test_from_url(self):
        with pytest.raises(TypeError, match=r".* a string .*"):
            TermImage.from_url(python_img)
        with pytest.raises(ValueError, match="Invalid URL.*"):
            TermImage.from_url(python_image)
        with pytest.raises(URLNotFoundError):
            TermImage.from_url(python_url + "e")
        with pytest.raises(UnidentifiedImageError):
            TermImage.from_url(
                "https://raw.githubusercontent.com/AnonymouX47/term-img/main/LICENSE"
            )

        image = TermImage.from_url(python_url)
        assert isinstance(image, TermImage)
        assert image.source == python_url
        assert os.path.exists(image._source)

        # Ensure size arguments get through
        with pytest.raises(ValueError, match=r".* both width and height"):
            TermImage.from_url(python_url, width=1, height=1)

        # Ensure scale argument gets through
        with pytest.raises(TypeError, match=r"'scale' .*"):
            TermImage.from_url(python_url, scale=1.0)


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

        image = TermImage.from_url(python_url)
        assert image.source == python_url

        with pytest.raises(AttributeError):
            image.source = None
