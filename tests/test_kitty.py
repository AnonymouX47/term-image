"""KittyImage-specific tests"""

import pytest

from term_image.image.kitty import LINES, WHOLE, KittyImage

from .common import *  # noqa:F401
from .common import python_img, setup_common


@pytest.mark.order("first")
def test_setup_common():
    setup_common(KittyImage)


def test_set_render_method():
    try:
        assert KittyImage._render_method == KittyImage._default_render_method == LINES
        image = KittyImage(python_img)
        assert image._render_method == KittyImage._default_render_method

        assert KittyImage.set_render_method(WHOLE) is True
        assert KittyImage._render_method == WHOLE
        assert image._render_method == WHOLE

        assert image.set_render_method(LINES) is True
        assert image._render_method == LINES

        assert image.set_render_method() is True
        assert image._render_method == WHOLE

        assert KittyImage.set_render_method(LINES) is True
        assert KittyImage._render_method == LINES
        assert image._render_method == LINES

        assert image.set_render_method(WHOLE) is True
        assert image._render_method == WHOLE

        assert image.set_render_method() is True
        assert image._render_method == LINES

        assert KittyImage.set_render_method(WHOLE) is True
        assert KittyImage._render_method == WHOLE
        assert image._render_method == WHOLE

        assert KittyImage.set_render_method() is True
        assert KittyImage._render_method == KittyImage._default_render_method
        assert image._render_method == KittyImage._default_render_method
    finally:
        KittyImage._render_method = KittyImage._default_render_method
