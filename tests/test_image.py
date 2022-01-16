import os
from shutil import get_terminal_size

import pytest
from PIL import Image, UnidentifiedImageError

from term_img.exceptions import URLNotFoundError
from term_img.image import TermImage

columns, lines = term_size = get_terminal_size()
rows = lines * 2

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

        size_ = min(columns, rows - 4)

        image = TermImage(python_img, width=size_)
        assert isinstance(image._original_size, tuple)
        assert image._size == (size_,) * 2

        image = TermImage(python_img, height=size_)
        assert isinstance(image._original_size, tuple)
        assert image._size == (size_,) * 2

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
