from shutil import get_terminal_size

import pytest
from PIL import Image

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

        image = TermImage(python_img, scale=(0.5, 0.4))
        assert isinstance(image._scale, list)
        assert image._scale == [0.5, 0.4]
