"""KittyImage-specific tests"""

import pytest

from term_image.image import KittyImage

from .common import *  # noqa:F401
from .common import setup_common


@pytest.mark.order("first")
def test_setup_common():
    setup_common(KittyImage)
