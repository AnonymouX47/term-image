import atexit
import os

import pytest
from PIL import Image, UnidentifiedImageError

from term_image.exceptions import URLNotFoundError
from term_image.image import BaseImage, BlockImage, ImageSource, from_url

python_image = "tests/images/python.png"
python_url = (
    "https://raw.githubusercontent.com/AnonymouX47/term-image/main/tests/"
    "images/python.png"
)
python_img = Image.open(python_image)


@atexit.register
def close_imgs():
    python_img.close()


def test_from_url():
    with pytest.raises(TypeError, match=r".* a string .*"):
        BlockImage.from_url(python_img)
    with pytest.raises(ValueError, match="Invalid URL.*"):
        BlockImage.from_url(python_image)
    with pytest.raises(URLNotFoundError):
        BlockImage.from_url(python_url + "e")
    with pytest.raises(UnidentifiedImageError):
        BlockImage.from_url(
            "https://raw.githubusercontent.com/AnonymouX47/term-image/main/LICENSE"
        )

    image = BlockImage.from_url(python_url)
    assert isinstance(image, BlockImage)
    assert image._url == python_url
    assert os.path.exists(image._source)
    assert image._source_type is ImageSource.URL

    # Ensure size arguments get through
    with pytest.raises(ValueError, match=r".* both width and height"):
        BlockImage.from_url(python_url, width=1, height=1)

    # Ensure scale argument gets through
    with pytest.raises(TypeError, match=r"'scale' .*"):
        BlockImage.from_url(python_url, scale=1.0)


def test_source():
    image = BlockImage.from_url(python_url)
    assert image.source == image._url == python_url
    assert image.source_type is ImageSource.URL


def test_close():
    image = BlockImage.from_url(python_url)
    source = image._source

    image.close()
    assert not os.path.exists(source)
    with pytest.raises(AttributeError):
        image._url


class TestConvinience:
    def test_from_url(self):
        with pytest.raises(TypeError, match=r"a string"):
            from_url(python_img)

        # Ensure size arguments get through
        with pytest.raises(ValueError, match=r"both width and height"):
            from_url(python_url, width=1, height=1)

        # Ensure scale argument gets through
        with pytest.raises(TypeError, match=r"'scale'"):
            from_url(python_url, scale=1.0)

        assert isinstance(from_url(python_url), BaseImage)
