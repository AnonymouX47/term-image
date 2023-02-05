import pytest
from PIL import Image

from term_image.image import BlockImage, KittyImage, Size
from term_image.utils import COLOR_RESET
from term_image.widget import UrwidImage, UrwidImageCanvas

_size = (30, 15)

python_file = "tests/images/python.png"
python_img = Image.open(python_file)
python_image = BlockImage(python_img)
trans = BlockImage.from_file("tests/images/trans.png")


class TestWidget:
    def test_args(self):
        for value in (python_file, python_img):
            with pytest.raises(TypeError, match="'image'"):
                UrwidImage(value)

        for value in (None, 2.0, 2):
            with pytest.raises(TypeError, match="'format'"):
                UrwidImage(python_image, value)
        for string in (".", "+"):
            with pytest.raises(ValueError, match="format specifier"):
                UrwidImage(python_image, string)

        for value in (None, 2.0, "2"):
            with pytest.raises(TypeError, match="'upscale'"):
                UrwidImage(python_image, upscale=value)

    def test_attributes(self):
        image_w = UrwidImage(python_image)
        assert all(name.startswith("_ti_") for name in vars(image_w))

    def test_image(self):
        image_w = UrwidImage(python_image)
        assert image_w.image is python_image


class TestRows:
    def test_upscale_false(self):
        image_w = UrwidImage(python_image)
        ori_size = python_image._valid_size(Size.ORIGINAL)
        fit_size = python_image._valid_size(ori_size[0] - 5)

        assert ori_size[1] != fit_size[1]
        assert image_w.rows((ori_size[0] - 5,)) == fit_size[1]
        assert image_w.rows((ori_size[0] + 5,)) == ori_size[1]

    def test_upscale_true(self):
        image_w = UrwidImage(python_image, upscale=True)
        ori_size = python_image._valid_size(Size.ORIGINAL)

        assert (
            image_w.rows((ori_size[0] - 5,))
            == image_w._ti_image._valid_size(ori_size[0] - 5)[1]
            != ori_size[1]
        )
        assert (
            image_w.rows((ori_size[0] + 5,))
            == image_w._ti_image._valid_size(ori_size[0] + 5)[1]
            != ori_size[1]
        )


class TestRender:
    class TestBox:
        def _test_output(self, canv, size, image_size):
            trans._size = image_size
            render = format(trans, f"{size[0]}.{size[1]}").splitlines()
            lines = canv._ti_lines

            assert canv.size == size
            assert len(lines) == size[1] == len(render)
            for line, render_line in zip(lines, render):
                assert isinstance(line, bytes)
                assert line.decode() == render_line + "\0\0"

        def test_smaller_than_original_size(self):
            not_upscaled = UrwidImage(trans)
            upscaled = UrwidImage(trans, upscale=True)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = tuple((x - 2 for x in ori_size))
            upscaled_canv = upscaled.render(size)
            not_upscaled_canv = not_upscaled.render(size)
            image_size = trans._valid_size(Size.FIT, maxsize=size)

            self._test_output(upscaled_canv, size, image_size)
            self._test_output(not_upscaled_canv, size, image_size)
            assert upscaled_canv._ti_lines == not_upscaled_canv._ti_lines

        def test_upscale_false(self):
            image_w = UrwidImage(trans)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = tuple((x + 2 for x in ori_size))
            canv = image_w.render(size)
            lines = canv._ti_lines

            self._test_output(canv, size, ori_size)

            # One padding line at both the top and bottom
            assert lines[0].rstrip(b"\0\0").isspace()
            assert not lines[1].rstrip(b"\0\0").isspace()
            assert not lines[-2].rstrip(b"\0\0").isspace()
            assert lines[-1].rstrip(b"\0\0").isspace()

            # One padding column on both ends of each line
            for line in lines:
                line = line.decode().rstrip("\0\0")
                if not line.isspace():
                    left, _, right = line.split(COLOR_RESET)
                    assert left == " "
                    assert right == " "

        def test_upscale_true(self):
            image_w = UrwidImage(trans, upscale=True)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = trans._valid_size(ori_size[0] + 2)
            canv = image_w.render(size)
            lines = canv._ti_lines
            image_size = trans._valid_size(Size.FIT, maxsize=size)

            # The image should have no padding; *size* is proportional to image size
            # and sizing is FIT.

            self._test_output(canv, size, image_size)
            assert not lines[0].rstrip(b"\0\0").isspace()
            assert not lines[-1].rstrip(b"\0\0").isspace()
            for line in lines:
                line = line.decode().rstrip("\0\0")
                if not line.isspace():
                    left, _, right = line.split(COLOR_RESET)
                    assert left == ""
                    assert right == ""

    class TestFlow:
        def _test_output(self, canv, size, image_size, upscaled):
            trans._size = image_size
            render = format(trans, f"{size[0]}.{image_size[1]}").splitlines()
            lines = canv._ti_lines

            assert canv.size == (size[0], image_size[1])
            assert len(lines) == image_size[1] == len(render)
            if upscaled:
                assert size[0] == image_size[0]
            for line, render_line in zip(lines, render):
                assert isinstance(line, bytes)
                assert line.decode() == render_line + "\0\0"

        def test_smaller_than_original_size(self):
            not_upscaled = UrwidImage(trans)
            upscaled = UrwidImage(trans, upscale=True)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = (ori_size[0] - 2,)
            upscaled_canv = upscaled.render(size)
            not_upscaled_canv = not_upscaled.render(size)
            image_size = trans._valid_size(size[0])

            self._test_output(upscaled_canv, size, image_size, True)
            self._test_output(not_upscaled_canv, size, image_size, False)
            assert upscaled_canv._ti_lines == not_upscaled_canv._ti_lines

        def test_upscale_false(self):
            image_w = UrwidImage(trans)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = (ori_size[0] + 2,)
            canv = image_w.render(size)
            lines = canv._ti_lines

            self._test_output(canv, size, ori_size, False)

            # No vertical padding
            assert not lines[1].rstrip(b"\0\0").isspace()
            assert not lines[-2].rstrip(b"\0\0").isspace()

            # One padding column on both ends of each line
            for line in lines:
                line = line.decode().rstrip("\0\0")
                if not line.isspace():
                    left, _, right = line.split(COLOR_RESET)
                    assert left == " "
                    assert right == " "

        def test_upscale_true(self):
            image_w = UrwidImage(trans, upscale=True)
            ori_size = trans._valid_size(Size.ORIGINAL)
            size = (ori_size[0] + 2,)
            canv = image_w.render(size)
            lines = canv._ti_lines

            # The image should have no padding

            self._test_output(canv, size, trans._valid_size(size[0]), True)
            assert not lines[0].rstrip(b"\0\0").isspace()
            assert not lines[-1].rstrip(b"\0\0").isspace()
            for line in lines:
                line = line.decode().rstrip("\0\0")
                if not line.isspace():
                    left, _, right = line.split(COLOR_RESET)
                    assert left == ""
                    assert right == ""


def test_ignore_padding():
    canvases_lines = [
        UrwidImage(python_image, fmt).render(_size)._ti_lines
        for fmt in ("", "200.200", "100.50")
    ]
    python_image.set_size(Size.AUTO, maxsize=_size)
    render = format(python_image, f"{_size[0]}.{_size[1]}").encode().splitlines()

    for render_line, line1, line2, line3 in zip(render, *canvases_lines):
        assert render_line + b"\0\0" == line1 == line2 == line3


# There's no need to test formatting separately since it uses the functionality of the
# underlying image


class TestCanvas:
    def test_cols(self):
        image_w = UrwidImage(python_image, upscale=True)
        canv = image_w.render(_size)
        assert canv.cols() == _size[0]

    def test_rows(self):
        image_w = UrwidImage(python_image, upscale=True)
        canv = image_w.render(_size)
        assert canv.rows() == _size[1]

    def test_content(self):
        image_w = UrwidImage(python_image, upscale=True)
        canv = image_w.render(_size)
        content = [line for [(*_, line)] in canv.content()]

        assert len(content) == len(canv._ti_lines)
        for content_line, line in zip(content, canv._ti_lines):
            assert content_line == line

    def test_disguise(self):
        image_w = UrwidImage(KittyImage(python_img), upscale=True)
        canv = image_w.render(_size)
        for disguise_state in (0, 1, 2, 0, 1, 2, 0):
            content = [line for [(*_, line)] in canv.content()]
            for line in content:
                line = line.decode()
                assert line.endswith("\0\0" + "\b " * disguise_state)
            UrwidImageCanvas._ti_change_disguise()
