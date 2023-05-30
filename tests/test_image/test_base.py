"""Render-style-independent tests"""

import atexit
import io
import os
import sys
from operator import floordiv, mul
from pathlib import Path

import pytest
from PIL import Image, UnidentifiedImageError

from term_image import set_cell_ratio
from term_image.ctlseqs import ESC
from term_image.exceptions import InvalidSizeError, TermImageError
from term_image.image import BaseImage, BlockImage, ImageIterator, ImageSource, Size
from term_image.image.common import _ALPHA_THRESHOLD

from .. import reset_cell_size_ratio
from .common import _size, columns, lines, python_img, setup_common

python_image = "tests/images/python.png"
python_sym = "tests/images/python_sym.png"  # Symlink to "python.png"
anim_img = Image.open("tests/images/lion.gif")
stdout = io.StringIO()

setup_common(BlockImage)
from .common import _height, _width  # noqa:E402


@atexit.register
def close_imgs():
    anim_img.close()


def clear_stdout():
    stdout.seek(0)
    stdout.truncate()


class BytesPath:
    def __init__(self, path: str) -> None:
        self.path = path

    def __fspath__(self) -> bytes:
        return self.path.encode()


class TestConstructor:
    def test_args(self):
        with pytest.raises(TypeError, match=r"'image'"):
            BlockImage(python_image)

        for size in ((0, 1), (1, 0), (0, 0)):
            with pytest.raises(ValueError, match=r"'image'"):
                BlockImage(Image.new("RGB", size))

        # Ensure size arguments get through to `set_size()`
        with pytest.raises(TypeError, match="'width' and 'height'"):
            BlockImage(python_img, width=1, height=Size.FIT)

    def test_init(self):
        image = BlockImage(python_img)
        assert image._size is Size.FIT
        assert image._source is python_img
        assert image._source_type is ImageSource.PIL_IMAGE
        assert isinstance(image._original_size, tuple)
        assert image._original_size == python_img.size

        image = BlockImage(python_img, width=None)
        assert image._size is Size.FIT
        image = BlockImage(python_img, height=None)
        assert image._size is Size.FIT
        image = BlockImage(python_img, width=None, height=None)
        assert image._size is Size.FIT

        image = BlockImage(python_img, width=_size)
        assert isinstance(image._size, tuple)
        image = BlockImage(python_img, height=_size)
        assert isinstance(image._size, tuple)

        for value in Size:
            image = BlockImage(python_img, width=value)
            assert isinstance(image._size, tuple)
            image = BlockImage(python_img, height=value)
            assert isinstance(image._size, tuple)

        image = BlockImage(python_img)
        assert image._is_animated is False

    def test_init_animated(self):
        image = BlockImage(anim_img)
        assert image._is_animated is True
        assert image._frame_duration == (anim_img.info.get("duration") or 100) / 1000
        assert image._seek_position == 0
        assert image._n_frames is None

        try:
            anim_img.seek(2)
            assert BlockImage(anim_img)._seek_position == 2
        finally:
            anim_img.seek(0)


class TestFromFile:
    def test_args(self):
        with pytest.raises(TypeError, match=r"'filepath'"):
            BlockImage.from_file(python_img)
        with pytest.raises(FileNotFoundError):
            BlockImage.from_file(python_image + "e")
        for dir_path in ("tests", Path("tests"), BytesPath("tests")):
            with pytest.raises(IsADirectoryError):
                BlockImage.from_file(dir_path)
        with pytest.raises(UnidentifiedImageError):
            BlockImage.from_file("LICENSE")

        # Ensure size arguments get through
        with pytest.raises(TypeError, match="'width' and 'height'"):
            BlockImage.from_file(python_image, width=1, height=Size.FIT)

    def test_filepath(self):
        for path in (python_image, Path(python_image), BytesPath(python_image)):
            image = BlockImage.from_file(path)
            assert isinstance(image, BlockImage)
            assert image.source == os.path.abspath(python_image)
            assert image.source_type is ImageSource.FILE_PATH

    @pytest.mark.skipif(
        not os.path.islink(python_sym),
        reason="The symlink is on or has passed through a platform or filesystem that "
        "doesn't support symlinks",
    )
    def test_symlink(self):
        image = BlockImage.from_file(python_sym)
        assert isinstance(image, BlockImage)
        assert image._source == os.path.abspath(python_sym)
        assert image._source_type is ImageSource.FILE_PATH


class TestProperties:
    def test_closed(self):
        image = BlockImage(python_img)
        assert not image.closed

        with pytest.raises(AttributeError):
            image.closed = True

        image.close()
        assert image.closed

    def test_forced_support(self):
        class A(BaseImage):
            pass

        class B(A):
            pass

        class C(B):
            pass

        for value in (1, 1.0, "1", ()):
            with pytest.raises(TypeError):
                A.forced_support = value

        assert not A.forced_support
        assert not B.forced_support
        assert not C.forced_support

        A.forced_support = True
        assert A.forced_support
        assert B.forced_support
        assert C.forced_support

        B.forced_support = False
        assert A.forced_support
        assert not B.forced_support
        assert not C.forced_support

        C.forced_support = False
        B.forced_support = True
        assert A.forced_support
        assert B.forced_support
        assert not C.forced_support

    def test_frame_duration(self):
        image = BlockImage(python_img)
        assert image.frame_duration is None
        image.frame_duration = 0.5
        assert image.frame_duration is None

        image = BlockImage(anim_img)
        assert image._frame_duration == (anim_img.info.get("duration") or 100) / 1000

        for duration in (0, 1, "0.1", "1", 0.3j):
            with pytest.raises(TypeError):
                image.frame_duration = duration
        for duration in (0.0, -0.1):
            with pytest.raises(ValueError):
                image.frame_duration = duration

        image.frame_duration = 0.5
        assert image.frame_duration == 0.5

    def test_height(self):
        image = BlockImage(python_img)
        assert image.height is Size.FIT

        image.height = _size
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        assert image.size[1] == _size == image.height

        for value in Size:
            image.height = value
            assert isinstance(image.size, tuple)
            assert isinstance(image.width, int)
            assert isinstance(image.height, int)

        image.height = None
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        size = image.size
        image.height = Size.FIT
        assert image.size == size

        for value in (0.1, "1", (1, 1), [1, 1]):
            with pytest.raises(TypeError):
                image.height = value
        for value in (-1, 0):
            with pytest.raises(ValueError):
                image.height = value

    def test_is_animated(self):
        image = BlockImage(python_img)
        assert not image.is_animated

        image = BlockImage(anim_img)
        assert image.is_animated

        with pytest.raises(AttributeError):
            image.is_animated = False

    def test_n_frames(self):
        image = BlockImage(python_img)
        assert image.n_frames == 1

        image = BlockImage(anim_img)
        assert 1 < image.n_frames == anim_img.n_frames
        assert image.n_frames == anim_img.n_frames  # Ensure consistency

        with pytest.raises(AttributeError):
            image.n_frames = 2

    def test_original_size(self):
        image = BlockImage(python_img)

        for value in (None, 0, 1, 0.1, "1", (1, 1), [1, 1]):
            with pytest.raises(AttributeError):
                image.original_size = value

        assert image.original_size == python_img.size
        assert isinstance(image.original_size, tuple)

    @reset_cell_size_ratio()
    def test_rendered_size_height_width(self):
        image = BlockImage(python_img)  # Square

        with pytest.raises(AttributeError):
            image.rendered_size = (_size,) * 2
        with pytest.raises(AttributeError):
            image.rendered_height = _size
        with pytest.raises(AttributeError):
            image.rendered_width = _size

        assert isinstance(image.rendered_size, tuple)
        assert isinstance(image.rendered_width, int)
        assert isinstance(image.rendered_height, int)

        image.width = _width

        assert isinstance(image.rendered_size, tuple)
        assert isinstance(image.rendered_width, int)
        assert isinstance(image.rendered_height, int)

        # The rendered size is independent of the cell ratio
        # Change in cell-ratio must not affect the image's rendered size
        set_cell_ratio(0.5)
        image.width = _width
        assert image.rendered_size == (_width, _height)
        set_cell_ratio(0.1)
        assert image.rendered_size == (_width, _height)

    def test_size(self):
        image = BlockImage(python_img)
        assert image.size is Size.FIT

        for value in (None, 0, 1, 0.1, "1", [1, 1]):
            with pytest.raises(TypeError):
                image.size = value

        for value in Size:
            image.size = value
            assert image.size is image.height is image.width is value

        for size in ((1, 1), (100, 50), (50, 100)):
            image.size = size
            assert image.size == size

    def test_source(self):
        image = BlockImage(python_img)
        assert image.source is python_img
        assert image.source_type is ImageSource.PIL_IMAGE

        for path in (python_image, Path(python_image), BytesPath(python_image)):
            image = BlockImage.from_file(path)
            assert image.source == os.path.abspath(python_image)
            assert image.source_type is ImageSource.FILE_PATH

        with pytest.raises(AttributeError):
            image.source = None

    @pytest.mark.skipif(
        not os.path.islink(python_sym),
        reason="The symlink is on or has passed through a platform or filesystem that "
        "doesn't support symlinks",
    )
    def test_source_symlink(self):
        image = BlockImage.from_file(python_sym)
        assert os.path.basename(image.source) == "python_sym.png"
        assert (
            image.source == os.path.abspath(python_sym) != os.path.realpath(python_sym)
        )
        assert image.source_type is ImageSource.FILE_PATH

    def test_width(self):
        image = BlockImage(python_img)
        assert image.width is Size.FIT

        image.width = _size
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        assert image.size[0] == _size == image.width

        for value in Size:
            image.width = value
            assert isinstance(image.size, tuple)
            assert isinstance(image.width, int)
            assert isinstance(image.height, int)

        image.width = None
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        size = image.size
        image.width = Size.FIT
        assert image.size == size

        for value in (0.1, "1", (1, 1), [1, 1]):
            with pytest.raises(TypeError):
                image.width = value
        for value in (-1, 0):
            with pytest.raises(ValueError):
                image.width = value


def test_close():
    image = BlockImage(python_img)
    image.close()
    assert image.closed
    with pytest.raises(AttributeError):
        image._source
    with pytest.raises(TermImageError):
        image.source
    with pytest.raises(TermImageError):
        str(image)
    with pytest.raises(TermImageError):
        format(image)
    with pytest.raises(TermImageError):
        image.draw()


def test_context_management():
    image = BlockImage(python_img)
    with image as image2:
        assert image2 is image
    assert image.closed


def test_iter():
    image = BlockImage(python_img)
    with pytest.raises(ValueError, match="not animated"):
        iter(image)

    anim_image = BlockImage(anim_img)
    image_it = iter(anim_image)
    assert isinstance(image_it, ImageIterator)
    assert image_it._image is anim_image


def test_seek_tell():
    # Non-animated
    image = BlockImage(python_img)
    assert image.tell() == 0
    image.seek(0)
    assert image.tell() == 0
    with pytest.raises(ValueError, match="out of range"):
        image.seek(1)
    assert image.tell() == 0

    # Animated
    image = BlockImage(anim_img)
    assert image.tell() == 0
    n_frames = anim_img.n_frames

    image.seek(2)
    assert image.tell() == 2

    with pytest.raises(ValueError, match="out of range"):
        image.seek(n_frames)
    assert image.tell() == 2

    image.seek(n_frames - 1)
    assert image.tell() == n_frames - 1

    with pytest.raises(ValueError, match="out of range"):
        image.seek(n_frames + 1)
    assert image.tell() == n_frames - 1

    image.seek(0)
    assert image.tell() == 0


class TestSetSize:
    image = BlockImage(python_img)  # Square
    h_image = BlockImage.from_file("tests/images/hori.jpg")  # Horizontally-oriented
    v_image = BlockImage.from_file("tests/images/vert.jpg")  # Vertically-oriented

    def test_args_width_height(self):
        for value in (1.0, "1", (), []):
            with pytest.raises(TypeError, match="'width'"):
                self.image.set_size(value)
            with pytest.raises(TypeError, match="'height'"):
                self.image.set_size(height=value)
        for value in (0, -1, -100):
            with pytest.raises(ValueError, match="'width'"):
                self.image.set_size(value)
            with pytest.raises(ValueError, match="'height'"):
                self.image.set_size(height=value)
        for width, height in ((1, Size.FIT), (Size.FIT, 1), (Size.FIT, Size.FIT)):
            with pytest.raises(TypeError, match="'width' and 'height'"):
                self.image.set_size(width, height)

    def test_args_frame_size(self):
        for value in (None, 1, 1.0, "1", (1.0, 1), (1, 1.0), ("1.0",), [1, 1]):
            with pytest.raises(TypeError, match="'frame_size'"):
                self.image.set_size(frame_size=value)
        for value in ((), (0,), (1,), (1, 1, 1)):
            with pytest.raises(ValueError, match="'frame_size'"):
                self.image.set_size(frame_size=value)

    def test_both_width_height(self):
        for size in ((1, 1), (100, 50), (50, 100)):
            self.image.set_size(*size)
            assert self.image.size == size

    @reset_cell_size_ratio()
    def test_frame_size_absolute(self):
        # Some of these assertions pass only when the cell ratio is about 0.5
        set_cell_ratio(0.5)

        self.image.set_size(frame_size=(100, 50))
        assert self.image.size == (100, 50)

        self.image.set_size(frame_size=(100, 55))
        assert self.image.size == (100, 50)

        self.image.set_size(frame_size=(110, 50))
        assert self.image.size == (100, 50)

        self.h_image.set_size(frame_size=(100, 50))
        assert self.h_image.width == 100

        self.v_image.set_size(frame_size=(100, 50))
        assert self.v_image.height == 50

    def test_frame_size_relative(self):
        self.h_image.set_size()
        assert self.h_image.width == columns

        self.v_image.set_size()
        assert self.v_image.height == lines - 2

        self.h_image.set_size(frame_size=(0, 0))
        assert self.h_image.width == columns

        self.v_image.set_size(frame_size=(0, 0))
        assert self.v_image.height == lines

        self.h_image.set_size(frame_size=(-3, 0))
        assert self.h_image.width == columns - 3

        self.v_image.set_size(frame_size=(0, -5))
        assert self.v_image.height == lines - 5

        self.image.set_size(frame_size=(-columns, -lines))
        assert self.image.size == (1, 1)

        self.image.set_size(frame_size=(-columns * 2, -lines * 2))
        assert self.image.size == (1, 1)

    @reset_cell_size_ratio()
    def test_can_exceed_frame_size(self):
        # These assertions pass only when the cell ratio is about 0.5
        set_cell_ratio(0.5)

        self.image.set_size(width=300, frame_size=(200, 100))
        assert self.image.size == (300, 150)

        self.image.set_size(height=150, frame_size=(200, 100))
        assert self.image.size == (300, 150)


def test_renderer():
    def test(img, *args, **kwargs):
        return img, args, kwargs

    image = BlockImage(python_img)

    for positionals, keywords in (
        ((), {}),
        ((2,), {"d": "dude"}),
        ((1, 2, 3), {"a": 1, "b": 2, "c": 3}),
    ):
        img, args, kwargs = image._renderer(test, *positionals, **keywords)
        assert isinstance(img, Image.Image)
        assert args == positionals
        assert kwargs == keywords


class TestRenderData:
    # Fully transparent image
    # It's easy to predict it's pixel values
    trans = BlockImage.from_file("tests/images/trans.png")
    trans.height = _size

    def get_render_data(self, img=None, alpha=None, **kwargs):
        return self.trans._get_render_data(
            img or self.trans._get_image(), alpha, **kwargs
        )

    def test_alpha(self):

        # float
        for alpha in (0.0, _ALPHA_THRESHOLD, 0.999):
            img, _, a = self.get_render_data(alpha=alpha)
            assert isinstance(img, Image.Image)
            assert img.mode == "RGBA"
            assert all(px == 0 for px in a)

            rgb_img = self.trans._get_image().convert("RGB")
            img, _, a = self.get_render_data(rgb_img, alpha)
            assert isinstance(img, Image.Image)
            assert img.mode == "RGB"
            assert all(px == 255 for px in a)

        # str
        for alpha in ("#ffffff", "#"):
            img, _, a = self.get_render_data(alpha=alpha)
            assert isinstance(img, Image.Image)
            assert img.mode == "RGB"
            assert all(px == 255 for px in a)

            rgb_img = self.trans._get_image().convert("RGB")
            img, _, a = self.get_render_data(rgb_img, alpha)
            assert isinstance(img, Image.Image)
            assert img.mode == "RGB"
            assert all(px == 255 for px in a)

        # None
        img, _, a = self.get_render_data(alpha=None)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert all(px == 255 for px in a)

        rgb_img = self.trans._get_image().convert("RGB")
        img, _, a = self.get_render_data(rgb_img, None)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert all(px == 255 for px in a)

    def test_size(self):
        for alpha in (_ALPHA_THRESHOLD, "#", None):
            render_size = self.trans._get_render_size()
            img, rgb, a = self.get_render_data(alpha=alpha)
            assert isinstance(img, Image.Image)
            assert img.size == render_size
            assert len(rgb) == len(a) == mul(*render_size)

            size = (47, 31)
            img, rgb, a = self.get_render_data(alpha=alpha, size=size)
            assert isinstance(img, Image.Image)
            assert img.size == size
            assert len(rgb) == len(a) == mul(*size)

    def test_pixel_data(self):
        for alpha in (_ALPHA_THRESHOLD, "#", None):
            img, rgb, a = self.get_render_data(alpha=alpha)
            assert isinstance(img, Image.Image)
            assert isinstance(rgb, list)
            assert isinstance(a, list)

            img, rgb, a = self.get_render_data(alpha=alpha, pixel_data=False)
            assert isinstance(img, Image.Image)
            assert rgb is None
            assert rgb is None

    def test_round_alpha(self):
        image = BlockImage(python_img, height=_size)
        img, rgb, a = image._get_render_data(python_img, alpha=_ALPHA_THRESHOLD)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        assert any(px not in {0, 255} for px in a)

        img, rounded_rgb, a = image._get_render_data(
            python_img, alpha=_ALPHA_THRESHOLD, round_alpha=True
        )
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        assert all(px in {0, 255} for px in a)

        assert rgb != rounded_rgb  # Blends rounded rgb with terminal BG

    def test_cleanup(self):
        def test(img, *, frame, fail=False):
            ori_size = image._original_size
            if fail:
                ori_img = img
                img = ori_img.copy()

            # resize (no convert)
            image._get_render_data(
                img, 0.5, size=tuple(map(floordiv, ori_size, (2, 2))), frame=frame
            )
            if fail:
                with pytest.raises(ValueError, match="closed"):
                    img.load()
                img = ori_img.copy()
            else:
                img.load()

            # convert (no resize)
            image._get_render_data(img, None, size=ori_size, frame=frame)
            if fail:
                with pytest.raises(ValueError, match="closed"):
                    img.load()
                img = ori_img.copy()
            else:
                img.load()

            # composite (no resize, no convert)
            for alpha in ("#ffffff", "#"):
                image._get_render_data(img, alpha, size=ori_size, frame=frame)
                if fail:
                    with pytest.raises(ValueError, match="closed"):
                        img.load()
                    img = ori_img.copy()
                else:
                    img.load()

            # alpha blend (no resize, no convert)
            image._get_render_data(
                img, 0.5, size=ori_size, round_alpha=True, frame=frame
            )
            if fail:
                with pytest.raises(ValueError, match="closed"):
                    img.load()
                img = ori_img.copy()
            else:
                img.load()

            # no manipulation (no closes)
            source = img if img is image._source else None
            for img in (img, img.convert("RGB")):
                try:
                    if source:
                        image._source = img
                    image._get_render_data(img, 0.5, size=ori_size, frame=frame)
                    img.load()
                finally:
                    if source:
                        image._source = source

        img = Image.open("tests/images/python.png")
        image = BlockImage(img)
        # Source
        test(img, frame=False)
        # Frame
        test(img.copy(), frame=True)
        # Source & Frame
        test(img, frame=True)
        # Not source & not frame
        test(img.copy(), frame=False, fail=True)


# As long as each subclass passes it's render tests (particulary those related to the
# size of the render results), then testing formatting with a single style should
# suffice.
class TestFormatting:
    image = BlockImage(python_img)
    image.set_size()
    full_width = image.width
    image.width //= 2  # To ensure there's padding
    render = str(image)
    check_formatting = staticmethod(image._check_formatting)

    def check_padding(self, *args, render=None, **kwargs):
        h_align, width, v_align, height, *_ = args + (None,) * 4
        for name, value in kwargs.items():
            exec(f"{name} = {value!r}")
        width = width or columns
        height = height or lines

        left, right = [], []
        render = self.image._format_render(render or self.render, *args, **kwargs)

        chunk, _, render = render.partition(ESC)
        top, _, first_left = chunk.rpartition("\n")
        left.append(first_left)

        chunk, _, render = render.partition("\n")
        right.append(chunk.rpartition("m")[2])

        render, _, chunk = render.rpartition("m")
        last_right, _, bottom = chunk.partition("\n")

        render, _, chunk = render.rpartition("\n")
        last_left = chunk.partition(ESC)[0]

        for chunk in render.splitlines():
            next_left, _, chunk = chunk.partition(ESC)
            left.append(next_left)
            right.append(chunk.rpartition("m")[2])

        left.append(last_left)
        right.append(last_right)
        top, bottom = top.splitlines(), bottom.splitlines()

        # unquote to debug padding
        """
        print(self.image.size)
        for name in ("left", "right", "top", "bottom"):
            side = vars()[name]
            print(f"------------ {name} - {len(side)} --------------")
            for line in side:
                print(f"{len(line)} {line!r}")
        raise ValueError
        """

        n_left = (
            0
            if h_align == "<"
            else width - self.image.rendered_width
            if h_align == ">"
            else (width - self.image.rendered_width) // 2
        )
        n_right = width - self.image.rendered_width - n_left
        n_top = (
            0
            if v_align == "^"
            else height - self.image.rendered_height
            if v_align == "_"
            else (height - self.image.rendered_height) // 2
        )
        n_bottom = height - self.image.rendered_height - n_top

        assert len(left) == self.image.rendered_height
        assert all(line == " " * n_left for line in left)
        assert len(right) == self.image.rendered_height
        assert all(line == " " * n_right for line in right)
        assert len(top) == n_top
        assert all(line == " " * width for line in top)
        assert len(bottom) == n_bottom
        assert all(line == " " * width for line in bottom)

        return left, right, top, bottom

    def test_args(self):
        self.image.set_size()
        for value in (1, 1.0, (), []):
            with pytest.raises(TypeError, match="'h_align'"):
                self.check_formatting(h_align=value)
            with pytest.raises(TypeError, match="'v_align'"):
                self.check_formatting(v_align=value)

        for value in ("", "cool", ".", " ", "\n"):
            with pytest.raises(ValueError, match="'h_align'"):
                self.check_formatting(h_align=value)
            with pytest.raises(ValueError, match="'v_align'"):
                self.check_formatting(v_align=value)

        for value in ("1", 1.0, (), []):
            with pytest.raises(TypeError, match="'pad_width'"):
                self.check_formatting(width=value)
            with pytest.raises(TypeError, match="'pad_height'"):
                self.check_formatting(height=value)

        for value in (0, -1, -100):
            with pytest.raises(ValueError, match="'pad_width'"):
                self.check_formatting(width=value)
            with pytest.raises(ValueError, match="'pad_height'"):
                self.check_formatting(height=value)

    def test_arg_align_conversion(self):
        self.image.set_size()
        assert self.check_formatting() == (None,) * 4

        for value in "<|>":
            assert self.check_formatting(h_align=value) == (value, None, None, None)
        for val1, val2 in zip(("left", "center", "right"), "<|>"):
            assert self.check_formatting(h_align=val1) == (val2, None, None, None)

        for value in "^-_":
            assert self.check_formatting(v_align=value) == (None, None, value, None)
        for val1, val2 in zip(("top", "middle", "bottom"), "^-_"):
            assert self.check_formatting(v_align=val1) == (None, None, val2, None)

    def test_arg_padding_width(self):
        self.image.set_size()
        for value in (1, _width, columns):
            assert self.check_formatting(width=value) == (None, value, None, None)

        # Can exceed terminal width
        assert self.check_formatting(width=columns + 1) == (
            None,
            columns + 1,
            None,
            None,
        )

    def test_arg_padding_height(self):
        self.image.set_size()
        for value in (1, _size, lines):
            assert self.check_formatting(height=value) == (None, None, None, value)

        # Can exceed terminal height
        assert self.check_formatting(height=lines + 1) == (None, None, None, lines + 1)

    def test_padding_width(self):
        self.image.width = self.full_width // 2
        for width in range(self.full_width, columns + 1):
            self.check_padding("<", width)
            self.check_padding("|", width)
            self.check_padding(">", width)
            self.check_padding(None, width)

    def test_padding_height(self):
        self.image.width = self.full_width // 2
        for height in range(self.full_width, lines + 1):
            self.check_padding(None, None, "^", height)
            self.check_padding(None, None, "-", height)
            self.check_padding(None, None, "_", height)
            self.check_padding(None, None, None, height)

    def test_align(self):
        self.image.width = self.full_width // 2
        self.check_padding("<", columns, "^", lines)
        self.check_padding("|", columns, "-", lines)
        self.check_padding(">", columns, "_", lines)

    def test_format_spec(self):
        for spec in (
            "1<",
            "-1.|1",
            "<1.1^",
            ".",
            "1.",
            "<.",
            ">1.",
            "-",
            "<^",
            ".#",
            ">1.#.23",
            "#0",
            "#.",
            "#2445",
            "#.23fa45",
            "#fffffff",
            "#a45gh4",
            "###",
            " ",
            # style-specific section
            "+",
            "20+",
            ".^+",
            "#+",
        ):
            with pytest.raises(ValueError, match=r"Invalid format specifier"):
                self.image._check_format_spec(spec)

        for spec in (
            "<",
            "1",
            ".1",
            "<1",
            ".^1",
            "|1.-1",
            "<1.-",
            ".-",
            "#",
            "##",
            "#123456",
            "#23af5b",
            "#23AF5B",
            "#23Af5B",
            "#abcdef",
            "#ABCDEF",
            "#AbCdEf",
            "#.4",
            "#.343545453453",
            "1.1#",
            "1.1##",
            "<.^#ffffff",
            "<.^#FFFFFF",
            "<.^#fFfFfF",
            "<1.^1#.2",
            f"<{columns}.^{lines}##",
        ):
            fmt = self.image._check_format_spec(spec)
            assert isinstance(fmt, tuple)


# Testing with one style should suffice for all since it's simply testing the method
# and nothing perculiar to the style
class TestDraw:
    image = BlockImage(python_img, width=_size)
    anim_image = BlockImage(anim_img, width=_size)

    def test_args(self):
        sys.stdout = stdout
        for value in (1, (), [], {}, b""):
            with pytest.raises(TypeError, match="'alpha'"):
                self.image.draw(alpha=value)

        for value in (-1.0, -0.1, 1.0, 1.1):
            with pytest.raises(ValueError, match="'alpha'"):
                self.image.draw(alpha=value)

        for value in ("f", "fffff", "fffffff", "12h45g", "-2343"):
            with pytest.raises(ValueError, match="Invalid hex color"):
                self.image.draw(alpha=value)

        with pytest.raises(ValueError, match="'pad_width'"):
            self.image.draw(pad_width=columns + 1)

        with pytest.raises(ValueError, match="'pad_height'"):
            self.anim_image.draw(pad_height=lines + 1)

        for value in (1, 1.0, "1", (), []):
            with pytest.raises(TypeError, match="'animate'"):
                self.anim_image.draw(animate=value)

        for arg in ("scroll", "check_size"):
            for value in (1, 1.0, "1", (), []):
                with pytest.raises(TypeError, match=f"{arg!r}"):
                    self.image.draw(**{arg: value})

    def test_size_validation(self):
        sys.stdout = stdout
        self.image._size = (columns + 1, 1)
        with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
            self.image.draw()

        self.image._size = (1, lines + 1)
        with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
            self.image.draw()

    class TestNonAnimated:
        image = BlockImage(python_img, width=_size)
        anim_image = BlockImage(anim_img, width=_size)

        def test_fit_to_width_width(self):
            sys.stdout = stdout
            self.image._size = (columns, lines + 1)
            with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
                self.image.draw()

        def test_fit_to_width_height(self):
            sys.stdout = stdout
            self.image._size = (columns, lines + 1)
            with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
                self.image.draw()

        def test_scroll(self):
            sys.stdout = stdout
            self.image._size = (columns, lines + 1)
            self.image.draw(scroll=True)
            assert stdout.getvalue().count("\n") == lines + 1
            clear_stdout()

        def test_check_size(self):
            sys.stdout = stdout
            self.image._size = (columns + 1, lines)
            self.image.draw(check_size=False)
            assert stdout.getvalue().count("\n") == lines
            clear_stdout()

    class TestAnimatedFalse:
        image = BlockImage(python_img, width=_size)
        anim_image = BlockImage(anim_img, width=_size)

        def test_fit_to_width_width(self):
            sys.stdout = stdout
            self.anim_image._size = (columns, lines + 1)
            with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
                self.anim_image.draw(animate=False)

        def test_fit_to_width_height(self):
            sys.stdout = stdout
            self.anim_image._size = (columns, lines + 1)
            with pytest.raises(InvalidSizeError, match="image cannot .* terminal size"):
                self.anim_image.draw(animate=False)

        def test_scroll(self):
            sys.stdout = stdout
            self.anim_image._size = (columns, lines + 1)
            self.anim_image.draw(scroll=True, animate=False)
            assert stdout.getvalue().count("\n") == lines + 1
            clear_stdout()

        def test_check_size(self):
            sys.stdout = stdout
            self.anim_image._size = (columns + 1, lines)
            self.anim_image.draw(animate=False, check_size=False)
            assert stdout.getvalue().count("\n") == lines
            clear_stdout()

    class TestAnimated:
        image = BlockImage(python_img)
        anim_image = BlockImage(anim_img)

        def test_fit_to_width_width(self):
            sys.stdout = stdout
            self.anim_image._size = (columns, lines + 1)
            with pytest.raises(
                InvalidSizeError, match="animation cannot .* terminal size"
            ):
                self.anim_image.draw()

        def test_fit_to_width_height(self):
            sys.stdout = stdout
            self.anim_image._size = (columns, lines + 1)
            with pytest.raises(
                InvalidSizeError, match="animation cannot .* terminal size"
            ):
                self.anim_image.draw()

        def test_scroll(self):
            sys.stdout = stdout
            self.anim_image._size = (columns, lines + 1)
            with pytest.raises(InvalidSizeError, match="rendered height .* animation"):
                self.anim_image.draw(scroll=True)

        def test_check_size(self):
            sys.stdout = stdout
            self.anim_image._size = (columns + 1, lines)
            with pytest.raises(
                InvalidSizeError, match="animation cannot .* terminal size"
            ):
                self.anim_image.draw(check_size=False)

        def test_fit_scroll_check_size(self):
            sys.stdout = stdout
            self.anim_image._size = (columns + 1, lines + 1)
            with pytest.raises(
                InvalidSizeError, match="animation cannot .* terminal size"
            ):
                self.anim_image.draw(scroll=True, check_size=False)
