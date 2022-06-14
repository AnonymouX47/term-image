"""ITerm2Image-specific tests"""

import pytest

from term_image.image.iterm2 import LINES, WHOLE, ITerm2Image

from .common import *  # noqa:F401
from .common import python_img, setup_common

for name in tuple(globals()):
    if name.endswith("_Text"):
        del globals()[name]


@pytest.mark.order("first")
def test_setup_common():
    setup_common(ITerm2Image)


def test_set_render_method():
    try:
        assert ITerm2Image._render_method == ITerm2Image._default_render_method == LINES
        image = ITerm2Image(python_img)
        assert image._render_method == ITerm2Image._default_render_method

        assert ITerm2Image.set_render_method(WHOLE) is None
        assert ITerm2Image._render_method == WHOLE
        assert image._render_method == WHOLE

        assert image.set_render_method(LINES) is None
        assert image._render_method == LINES

        assert image.set_render_method() is None
        assert image._render_method == WHOLE

        assert ITerm2Image.set_render_method(LINES) is None
        assert ITerm2Image._render_method == LINES
        assert image._render_method == LINES

        assert image.set_render_method(WHOLE) is None
        assert image._render_method == WHOLE

        assert image.set_render_method() is None
        assert image._render_method == LINES

        assert ITerm2Image.set_render_method(WHOLE) is None
        assert ITerm2Image._render_method == WHOLE
        assert image._render_method == WHOLE

        assert ITerm2Image.set_render_method() is None
        assert ITerm2Image._render_method == ITerm2Image._default_render_method
        assert image._render_method == ITerm2Image._default_render_method
    finally:
        ITerm2Image._render_method = ITerm2Image._default_render_method
