"""BlockImage-specific tests"""

from term_image.ctlseqs import SGR_BG_DIRECT, SGR_NORMAL
from term_image.image import BlockImage
from term_image.image.common import _ALPHA_THRESHOLD

from .. import set_fg_bg_colors
from . import common
from .common import _size, setup_common


def test_setup_common():
    setup_common(BlockImage)


for name, obj in vars(common).items():
    if name.endswith(("_All", "_Text")):
        globals()[name] = obj


class TestRender:
    # Fully transparent image
    # It's easy to predict it's pixel values
    trans = BlockImage.from_file("tests/images/trans.png")
    trans.height = _size

    def render_image(self, alpha):
        return self.trans._renderer(self.trans._render_image, alpha)

    def test_size(self):
        render = self.render_image(_ALPHA_THRESHOLD)
        # No '\n' after the last line, hence the `+ 1`
        assert render.count("\n") + 1 == self.trans.height
        assert render.partition("\n")[0].count(" ") == self.trans.width

    def test_transparency(self):
        # Transparency enabled
        render = self.render_image(_ALPHA_THRESHOLD)
        assert render == str(self.trans) == f"{self.trans:1.1}"
        assert all(
            line == SGR_NORMAL + " " * self.trans.width + SGR_NORMAL
            for line in render.splitlines()
        )
        # Transparency disabled
        render = self.render_image(None)
        assert render == f"{self.trans:1.1#}"
        assert all(
            line == SGR_BG_DIRECT % (0, 0, 0) + " " * self.trans.width + SGR_NORMAL
            for line in render.splitlines()
        )

    def test_background_colour(self):
        # Terminal BG
        for bg in ((0,) * 3, (100,) * 3, (255,) * 3, None):
            set_fg_bg_colors(bg=bg)
            bg = bg or (0, 0, 0)
            render = self.render_image("#")
            assert render == f"{self.trans:1.1##}"
            assert all(
                line == SGR_BG_DIRECT % bg + " " * self.trans.width + SGR_NORMAL
                for line in render.splitlines()
            )
        set_fg_bg_colors((0, 0, 0), (0, 0, 0))
        # red
        render = self.render_image("#ff0000")
        assert render == f"{self.trans:1.1#ff0000}"
        assert all(
            line == SGR_BG_DIRECT % (255, 0, 0) + " " * self.trans.width + SGR_NORMAL
            for line in render.splitlines()
        )
        # green
        render = self.render_image("#00ff00")
        assert render == f"{self.trans:1.1#00ff00}"
        assert all(
            line == SGR_BG_DIRECT % (0, 255, 0) + " " * self.trans.width + SGR_NORMAL
            for line in render.splitlines()
        )
        # blue
        render = self.render_image("#0000ff")
        assert render == f"{self.trans:1.1#0000ff}"
        assert all(
            line == SGR_BG_DIRECT % (0, 0, 255) + " " * self.trans.width + SGR_NORMAL
            for line in render.splitlines()
        )
        # white
        render = self.render_image("#ffffff")
        assert render == f"{self.trans:1.1#ffffff}"
        assert all(
            line
            == SGR_BG_DIRECT % (255, 255, 255) + " " * self.trans.width + SGR_NORMAL
            for line in render.splitlines()
        )
