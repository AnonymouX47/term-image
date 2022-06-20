"""BlockImage-specific tests"""

from random import random

import pytest

from term_image.image import BlockImage
from term_image.image.common import _ALPHA_THRESHOLD
from term_image.utils import COLOR_RESET, CSI, get_fg_bg_colors

from . import common
from .common import _size, setup_common

for name, obj in vars(common).items():
    if name.endswith(("_All", "_Text")):
        globals()[name] = obj


def _is_on_kitty():
    return False


BlockImage._is_on_kitty = staticmethod(_is_on_kitty)


@pytest.mark.order("first")
def test_setup_common():
    setup_common(BlockImage)


class TestRender:
    # Fully transparent image
    # It's easy to predict it's pixel values
    trans = BlockImage.from_file("tests/images/trans.png")
    trans.height = _size

    def render_image(self, alpha):
        return self.trans._renderer(lambda im: self.trans._render_image(im, alpha))

    def test_size(self):
        self.trans.scale = 1.0
        render = self.render_image(_ALPHA_THRESHOLD)
        # No '\n' after the last line, hence the `+ 1`
        assert render.count("\n") + 1 == self.trans.height
        assert render.partition("\n")[0].count(" ") == self.trans.width

    def test_transparency(self):
        self.trans.scale = 1.0

        # Transparency enabled
        assert all(
            line == COLOR_RESET + " " * self.trans.width + COLOR_RESET
            for line in self.render_image(_ALPHA_THRESHOLD).splitlines()
        )
        # Transparency disabled
        assert all(
            line == f"{CSI}48;2;0;0;0m" + " " * self.trans.width + COLOR_RESET
            for line in self.render_image(None).splitlines()
        )

    def test_background_colour(self):
        self.trans.scale = 1.0

        # Terminal BG
        r, g, b = get_fg_bg_colors()[1] or (0, 0, 0)
        assert all(
            line == f"{CSI}48;2;{r};{g};{b}m" + " " * self.trans.width + COLOR_RESET
            for line in self.render_image("#").splitlines()
        )
        # red
        assert all(
            line == f"{CSI}48;2;255;0;0m" + " " * self.trans.width + COLOR_RESET
            for line in self.render_image("#ff0000").splitlines()
        )
        # green
        assert all(
            line == f"{CSI}48;2;0;255;0m" + " " * self.trans.width + COLOR_RESET
            for line in self.render_image("#00ff00").splitlines()
        )
        # blue
        assert all(
            line == f"{CSI}48;2;0;0;255m" + " " * self.trans.width + COLOR_RESET
            for line in self.render_image("#0000ff").splitlines()
        )
        # white
        assert all(
            line == f"{CSI}48;2;255;255;255m" + " " * self.trans.width + COLOR_RESET
            for line in self.render_image("#ffffff").splitlines()
        )

    def test_scaled(self):
        # At varying scales
        for self.trans.scale in map(lambda x: x / 100, range(10, 101)):
            render = self.render_image(_ALPHA_THRESHOLD)
            assert render.count("\n") + 1 == self.trans.rendered_height
            assert all(
                line == COLOR_RESET + " " * self.trans.rendered_width + COLOR_RESET
                for line in render.splitlines()
            )

        # Random scales
        for _ in range(100):
            scale = random()
            if scale == 0.0:
                continue
            self.trans.scale = scale
            if 0 in self.trans.rendered_size:
                continue
            render = self.render_image(_ALPHA_THRESHOLD)
            assert render.count("\n") + 1 == self.trans.rendered_height
            assert all(
                line == COLOR_RESET + " " * self.trans.rendered_width + COLOR_RESET
                for line in render.splitlines()
            )
