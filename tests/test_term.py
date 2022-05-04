"""TermImage-specific tests"""

from random import random

from term_image.image import TermImage
from term_image.image.common import _ALPHA_THRESHOLD

from .common import _size, setup_common


def test_setup_common():
    setup_common(TermImage)


# Must come after setup
from .common import *  # noqa:F401,E402


class TestRender:
    # Fully transparent image
    # It's easy to predict it's pixel values
    trans = TermImage.from_file("tests/images/trans.png")

    def render_image(self, alpha):
        return self.trans._renderer(lambda im: self.trans._render_image(im, alpha))

    def test_transparency(self):
        self.trans.set_size(height=_size)
        self.trans.scale = 1.0

        render = self.render_image(_ALPHA_THRESHOLD)
        # No '\n' after the last line, hence the `+ 1`
        assert render.count("\n") + 1 == self.trans.height
        assert render.partition("\n")[0].count(" ") == self.trans.width

        # Transparency enabled
        assert all(
            line == "\033[0m" + " " * self.trans.width + "\033[0m"
            for line in self.render_image(_ALPHA_THRESHOLD).splitlines()
        )
        # Transparency disabled
        assert all(
            line == "\033[48;2;0;0;0m" + " " * self.trans.width + "\033[0m"
            for line in self.render_image(None).splitlines()
        )

    def test_background_colour(self):
        self.trans.set_size(height=_size)
        self.trans.scale = 1.0

        # white
        assert all(
            line == "\033[48;2;255;255;255m" + " " * self.trans.width + "\033[0m"
            for line in self.render_image("#ffffff").splitlines()
        )
        # red
        assert all(
            line == "\033[48;2;255;0;0m" + " " * self.trans.width + "\033[0m"
            for line in self.render_image("#ff0000").splitlines()
        )

    def test_scaled(self):
        self.trans.set_size(height=_size)

        # At varying scales
        for self.trans.scale in map(lambda x: x / 100, range(10, 101)):
            if 0 not in self.trans.rendered_size:
                render = self.render_image(_ALPHA_THRESHOLD)
            assert render.count("\n") + 1 == self.trans.rendered_height
            assert render.partition("\n")[0].count(" ") == self.trans.rendered_width

        # Random scales
        for _ in range(100):
            scale = random()
            if scale == 0:
                continue
            self.trans.scale = scale
            if 0 in self.trans.rendered_size:
                continue
            render = self.render_image(_ALPHA_THRESHOLD)
            assert render.count("\n") + 1 == self.trans.rendered_height
            assert render.partition("\n")[0].count(" ") == self.trans.rendered_width
