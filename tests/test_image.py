import io
import os
import sys
from operator import gt, lt
from random import random
from shutil import get_terminal_size
from types import SimpleNamespace

import pytest
from PIL import Image, UnidentifiedImageError

from term_image import get_font_ratio, set_font_ratio
from term_image.exceptions import InvalidSize
from term_image.image import _ALPHA_THRESHOLD, ImageIterator, TermImage


def clear_stdout():
    stdout.seek(0)
    stdout.truncate()


def width_height(image, *, w=None, h=None):
    return (
        TermImage._pixels_lines(
            pixels=round(
                TermImage._width_height_px(
                    image,
                    w=TermImage._pixels_cols(cols=w),
                )
            )
        )
        if w is not None
        else TermImage._pixels_cols(
            pixels=round(
                TermImage._width_height_px(
                    image,
                    h=TermImage._pixels_lines(lines=h),
                )
            )
        )
    )


columns, lines = term_size = get_terminal_size()

# For square images
dummy = SimpleNamespace()
dummy._original_size = (1, 1)
if TermImage._pixels_cols(cols=columns) < TermImage._pixels_lines(lines=lines - 2):
    _width = columns
    _height = width_height(dummy, w=columns)
else:
    _height = lines - 2
    _width = width_height(dummy, h=lines - 2)
_width_px = TermImage._pixels_cols(cols=_width)
_height_px = TermImage._pixels_lines(lines=_height)

_size = 20

python_image = "tests/images/python.png"

python_sym = "tests/images/python_sym.png"  # Symlink to "python.png"
python_img = Image.open(python_image)
anim_img = Image.open("tests/images/lion.gif")

stdout = io.StringIO()


class TestConstructor:
    def test_args(self):
        with pytest.raises(TypeError, match=r"'PIL\.Image\.Image' instance"):
            TermImage(python_image)

        # Ensure size arguments get through to `set_size()`
        with pytest.raises(ValueError, match=r".* both width and height"):
            TermImage(python_img, width=1, height=1)

        with pytest.raises(TypeError, match=r"'scale'"):
            TermImage(python_img, scale=0.5)
        for value in ((0.0, 0.0), (-0.4, -0.4)):
            with pytest.raises(ValueError, match=r"'scale'"):
                TermImage(python_img, scale=value)

    def test_init(self):
        image = TermImage(python_img)
        assert image._size is None
        assert isinstance(image._scale, list)
        assert image._scale == [1.0, 1.0]
        assert image._source is python_img
        assert isinstance(image._original_size, tuple)
        assert image._original_size == python_img.size

        image = TermImage(python_img, width=_size)
        assert isinstance(image._size, tuple)
        image = TermImage(python_img, height=_size)
        assert isinstance(image._size, tuple)

        image = TermImage(python_img, scale=(0.5, 0.4))
        assert image._scale == [0.5, 0.4]

        assert image._is_animated is False

    def test_init_animated(self):
        image = TermImage(anim_img)
        assert image._is_animated is True
        assert image._frame_duration == (anim_img.info.get("duration") or 100) / 1000
        assert image._seek_position == 0
        assert image._n_frames is None


class TestFromFile:
    def test_args(self):
        with pytest.raises(TypeError, match=r"a string"):
            TermImage.from_file(python_img)
        with pytest.raises(FileNotFoundError):
            TermImage.from_file(python_image + "e")
        with pytest.raises(IsADirectoryError):
            TermImage.from_file("tests")
        with pytest.raises(UnidentifiedImageError):
            TermImage.from_file("LICENSE")

        # Ensure size arguments get through
        with pytest.raises(ValueError, match=r"both width and height"):
            TermImage.from_file(python_image, width=1, height=1)

        # Ensure scale argument gets through
        with pytest.raises(TypeError, match=r"'scale'"):
            TermImage.from_file(python_image, scale=1.0)

    def test_filepath(self):
        image = TermImage.from_file(python_image)
        assert isinstance(image, TermImage)
        assert image._source == os.path.abspath(python_image)

    @pytest.mark.skipif(
        not os.path.islink(python_sym),
        reason="The symlink is on or has passed through a platform or filesystem that "
        "doesn't support symlinks",
    )
    def test_symlink(self):
        image = TermImage.from_file(python_sym)
        assert isinstance(image, TermImage)


class TestProperties:
    def test_closed(self):
        image = TermImage(python_img)
        assert not image.closed

        with pytest.raises(AttributeError):
            image.closed = True

        image.close()
        assert image.closed

    def test_frame_duration(self):
        image = TermImage(python_img)
        assert image.frame_duration is None
        image.frame_duration = 0.5
        assert image.frame_duration is None

        image = TermImage(anim_img)
        assert image._frame_duration == (anim_img.info.get("duration") or 100) / 1000

        for duration in (0, 1, "0.1", "1", 0.3j):
            with pytest.raises(TypeError):
                image.frame_duration = duration
        for duration in (0.0, -0.1):
            with pytest.raises(ValueError):
                image.frame_duration = duration

        image.frame_duration = 0.5
        assert image.frame_duration == 0.5

    def test_is_animated(self):
        image = TermImage(python_img)
        assert not image.is_animated

        image = TermImage(anim_img)
        assert image.is_animated

        with pytest.raises(AttributeError):
            image.is_animated = False

    def test_n_frames(self):
        image = TermImage(python_img)
        assert image.n_frames == 1

        image = TermImage(anim_img)
        n_frames = image.n_frames  # On-demand computation
        assert n_frames > 1
        assert image.n_frames == image._n_frames == n_frames

        with pytest.raises(AttributeError):
            image.n_frames = 2

    def test_rendered_size_height_width(self):
        image = TermImage(python_img)  # Square

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

        # Varying scales
        for value in range(1, 101):
            scale = value / 100
            image.scale = scale
            assert image.rendered_width == round(_width * scale)
            assert image.rendered_height == round(_height * scale)

        # Random scales
        for _ in range(100):
            scale = random()
            try:
                image.scale = scale
            except ValueError:
                continue
            assert image.rendered_width == round(_width * scale)
            assert image.rendered_height == round(_height * scale)

        image.scale = 1.0

        # The rendered size is independent of the font ratio
        # Change in font-ratio must not affect the image's rendered size
        try:
            set_font_ratio(0.5)
            image.width = _width
            assert image.rendered_size == (_width, _height)
            set_font_ratio(0.1)
            assert image.rendered_size == (_width, _height)
        finally:
            set_font_ratio(0.5)

    def test_scale_x_y(self):
        image = TermImage(python_img)
        assert image.scale == (1.0, 1.0)
        assert image.scale_x == image.scale_y == 1.0

        assert isinstance(image.scale, tuple)
        assert isinstance(image.scale_x, float)
        assert isinstance(image.scale_y, float)

        for value in (0, 1, None, "1", "1.0"):
            with pytest.raises(TypeError):
                image.scale = value
            with pytest.raises(TypeError):
                image.scale_x = value
            with pytest.raises(TypeError):
                image.scale_y = value

        for value in (0.0, -0.1, 1.0001, 2.0):
            with pytest.raises(ValueError):
                image.scale = value
            with pytest.raises(ValueError):
                image.scale_x = value
            with pytest.raises(ValueError):
                image.scale_y = value

        for value in ((1, 1), (1.0, 1), (1, 1.0), ("1.0",)):
            with pytest.raises(TypeError):
                image.scale = value

        for value in (
            (0.5,),
            (0.5,) * 3,
            (0.0, 0.5),
            (0.5, 0.0),
            (-0.5, 0.5),
            (0.5, -0.5),
            (1.1, 0.5),
            (0.5, 1.1),
        ):
            with pytest.raises(ValueError):
                image.scale = value

        image.scale = 0.5
        assert image.scale == (0.5,) * 2
        assert image.scale_x == image.scale_y == 0.5

        image.scale_x = 0.25
        assert image.scale_x == image.scale[0] == 0.25
        assert image.scale_y == 0.5

        image.scale_y = 0.75
        assert image.scale_y == image.scale[1] == 0.75
        assert image.scale_x == 0.25

    def test_size_height_width(self):
        image = TermImage(python_img)
        assert image.original_size == python_img.size
        assert image.size is image.height is image.width is None

        image.width = _size
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        assert image.size[0] == _size == image.width

        image.height = 1
        assert isinstance(image.size, tuple)
        assert isinstance(image.width, int)
        assert isinstance(image.height, int)
        assert image.size[1] == 1 == image.height

        for size in (0, 1, 0.1, "1", (1, 1), [1, 1]):
            with pytest.raises(TypeError):
                image.size = size
        image.size = None
        assert image.size is image.height is image.width is None

    def test_source(self):
        image = TermImage(python_img)
        assert image.source is python_img

        image = TermImage.from_file(python_image)
        assert image.source == os.path.abspath(python_image)

        with pytest.raises(AttributeError):
            image.source = None

        # Symlinked image file
        linked_image = "tests/images/python_sym.png"
        # The file might not be a symlink if it is on or has passed through a
        # filesystem not supporting symlinks
        if os.path.islink(linked_image):
            image = TermImage.from_file(linked_image)
            assert os.path.basename(image.source) == "python_sym.png"
            assert (
                image.source
                == os.path.abspath(linked_image)
                != os.path.realpath(linked_image)
            )


def test_seek_tell():
    # Non-animated
    image = TermImage(python_img)
    assert image.tell() == 0
    image.seek(0)
    assert image.tell() == 0
    with pytest.raises(ValueError, match="out of range"):
        image.seek(1)
    assert image.tell() == 0

    # Animated
    image = TermImage(anim_img)
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


def test_set_size():
    def proportional(image):
        ori_width, ori_height = image.original_size
        # The converted width and height in pixels might not be exactly proportional
        # as they have been previously rounded to meet cell boundaries but the
        # difference must be less than the number of pixels for one line
        if _width_px < _height_px:
            # Height was adjusted
            return (
                abs(
                    image._pixels_cols(cols=image.width) / ori_width
                    # Was adjusted by multiplying, so we divide
                    - (image._pixels_lines(lines=image.height) / (get_font_ratio() * 2))
                    / ori_height
                )
                < image._pixels_lines(lines=1) / ori_height
            )
        else:
            # Width was adjusted
            return (
                abs(
                    # Was adjusted by dividing, so we multiply
                    (image._pixels_cols(cols=image.width) * (get_font_ratio() * 2))
                    / ori_width
                    - image._pixels_lines(lines=image.height) / ori_height
                )
                < image._pixels_lines(lines=1) / ori_height
            )

    image = TermImage(python_img)  # Square
    h_image = TermImage.from_file("tests/images/hori.jpg")
    v_image = TermImage.from_file("tests/images/vert.jpg")

    # Default args
    image.set_size()
    assert image._size == (_width, _height)
    h_image.set_size()
    assert gt(
        h_image._pixels_cols(cols=h_image.width),
        h_image._pixels_lines(lines=h_image.height),
    )
    v_image.set_size()
    assert lt(
        v_image._pixels_cols(cols=v_image.width),
        v_image._pixels_lines(lines=v_image.height),
    )

    # width and height
    with pytest.raises(ValueError, match=".* both width and height"):
        image.set_size(1, 1)
    for value in (1.0, "1", (), []):
        with pytest.raises(TypeError, match="'width' must be"):
            image.set_size(value)
        with pytest.raises(TypeError, match="'height' must be"):
            image.set_size(height=value)
    for value in (0, -1, -100):
        with pytest.raises(ValueError, match="'width' must be"):
            image.set_size(value)
        with pytest.raises(ValueError, match="'height' must be"):
            image.set_size(height=value)

    # h_allow and v_allow
    for value in (1.0, "1", (), []):
        with pytest.raises(TypeError, match="'h_allow' must be"):
            image.set_size(h_allow=value)
        with pytest.raises(TypeError, match="'v_allow' must be"):
            image.set_size(v_allow=value)
    for value in (-1, -100):
        with pytest.raises(ValueError, match="'h_allow' must be"):
            image.set_size(h_allow=value)
        with pytest.raises(ValueError, match="'v_allow' must be"):
            image.set_size(v_allow=value)

    # maxsize
    for value in (1, 1.0, "1", (1.0, 1), (1, 1.0), ("1.0",)):
        with pytest.raises(TypeError, match="'maxsize' must be"):
            image.set_size(maxsize=value)
    for value in ((), (0,), (1,), (1, 1, 1), (0, 1), (1, 0), (-1, 1), (1, -1)):
        with pytest.raises(ValueError, match="'maxsize' must contain"):
            image.set_size(maxsize=value)

    # fit_to_width and fit_to_height
    with pytest.raises(ValueError, match="mutually exclusive"):
        image.set_size(fit_to_width=True, fit_to_height=True)
    for arg in ("fit_to_width", "fit_to_height"):
        for value in (1, 1.0, "1", (), []):
            with pytest.raises(TypeError, match=f"{arg!r} .* boolean"):
                image.set_size(**{arg: value})
        with pytest.raises(ValueError, match=f"{arg!r} .* 'width' is given"):
            image.set_size(width=1, **{arg: True})
        with pytest.raises(ValueError, match=f"{arg!r} .* 'height' is given"):
            image.set_size(height=1, **{arg: True})
        with pytest.raises(ValueError, match=f"{arg!r} .* 'maxsize' is given"):
            image.set_size(maxsize=(1, 1), **{arg: True})

    # Cannot exceed maxsize
    with pytest.raises(InvalidSize, match="will not fit into"):
        image.set_size(width=101, maxsize=(100, 50))  # Exceeds on both axes
    with pytest.raises(InvalidSize, match="will not fit into"):
        image.set_size(width=101, maxsize=(100, 100))  # Exceeds horizontally
    with pytest.raises(InvalidSize, match="will not fit into"):
        image.set_size(height=51, maxsize=(200, 50))  # Exceeds Vertically
    # # Horizontal image in a square space, constrained by height
    with pytest.raises(InvalidSize, match="will not fit into"):
        h_image.set_size(height=100, maxsize=(100, 50))
    # # Vertical image in a square space, constrained by width
    with pytest.raises(InvalidSize, match="will not fit into"):
        v_image.set_size(width=100, maxsize=(100, 50))

    # Can exceed available terminal size
    image.set_size(width=columns + 1)
    assert image.width == columns + 1
    assert proportional(image)
    image.set_size(height=lines + 1)
    assert image.height == lines + 1
    assert proportional(image)

    # Proportionality
    image.set_size(width=_width)
    assert proportional(image)
    image.set_size(height=_height)
    assert proportional(image)

    h_image.set_size(width=_size)
    assert proportional(image)

    v_image.set_size(height=_size)
    assert proportional(image)

    # # Auto sizing
    image.set_size()
    assert proportional(image)
    image.set_size()
    assert proportional(image)

    # Fitted axes and proportionality
    h_image.set_size(fit_to_height=True)
    assert h_image.height == lines - 2
    assert proportional(image)

    v_image.set_size(fit_to_width=True)
    assert v_image.width == columns
    assert proportional(image)

    # Allowance
    image.set_size(fit_to_width=True)
    assert image.width == columns

    image.set_size(fit_to_height=True)
    assert image.height == lines - 2

    image.set_size(h_allow=2, fit_to_width=True)
    assert image.width == columns - 2

    image.set_size(v_allow=3, fit_to_height=True)
    assert image.height == lines - 3

    # maxsize + allowance nullification
    image.set_size(h_allow=2, v_allow=3, maxsize=(100, 55))
    assert image._size == (100, 50)
    image.set_size(h_allow=2, v_allow=3, maxsize=(110, 50))
    assert image._size == (100, 50)

    # Font ratio adjustment
    try:
        for ratio in (0.01, 0.1, 0.25, 0.4, 0.45, 0.55, 0.6, 0.75, 0.9, 0.99, 1.0):
            set_font_ratio(ratio)
            image.set_size()
            assert proportional(image)
    finally:
        set_font_ratio(0.5)  # Reset


def test_renderer():
    def test(img, *args, **kwargs):
        return img, args, kwargs

    image = TermImage(python_img)

    for positionals, keywords in (
        ((), {}),
        ((2,), {"d": "dude"}),
        ((1, 2, 3), {"a": 1, "b": 2, "c": 3}),
    ):
        img, args, kwargs = image._renderer(test, *positionals, **keywords)
        assert isinstance(img, Image.Image)
        assert args == positionals
        assert kwargs == keywords


def test_render():
    def render_image(alpha):
        return trans._renderer(lambda im: trans._render_image(im, alpha))

    trans = TermImage.from_file("tests/images/trans.png")

    for trans._size in ((1, 0), (0, 1), (0, 0)):
        with pytest.raises(ValueError, match="too small"):
            render_image(None)

    trans.set_size(height=_size)

    render = render_image(_ALPHA_THRESHOLD)
    # No '\n' after the last line, hence the `+ 1`
    assert render.count("\n") + 1 == trans.height
    assert render.partition("\n")[0].count(" ") == trans.width

    # Transparency enabled
    assert all(
        line == "\033[0m" + " " * trans.width + "\033[0m"
        for line in render_image(_ALPHA_THRESHOLD).splitlines()
    )
    # Transparency disabled
    assert all(
        line == "\033[48;2;0;0;0m" + " " * trans.width + "\033[0m"
        for line in render_image(None).splitlines()
    )
    # Color fill (white)
    assert all(
        line == "\033[48;2;255;255;255m" + " " * trans.width + "\033[0m"
        for line in render_image("#ffffff").splitlines()
    )
    # Color fill (red)
    assert all(
        line == "\033[48;2;255;0;0m" + " " * trans.width + "\033[0m"
        for line in render_image("#ff0000").splitlines()
    )

    # Scaled renders
    trans.set_size(_size)

    trans.scale = 0.0001
    with pytest.raises(ValueError, match="too small"):
        render_image(None)

    # At varying scales
    for trans.scale in map(lambda x: x / 100, range(10, 101)):
        try:
            render = render_image(_ALPHA_THRESHOLD)
        except ValueError:
            continue
        assert render.count("\n") + 1 == trans.rendered_height
        assert render.partition("\n")[0].count(" ") == trans.rendered_width

    # Random scales
    for _ in range(100):
        try:
            trans.scale = random()
            render = render_image(_ALPHA_THRESHOLD)
        except ValueError:  # random value == 0 or scale is too small
            continue
        assert render.count("\n") + 1 == trans.rendered_height
        assert render.partition("\n")[0].count(" ") == trans.rendered_width

    image = TermImage(python_img, width=_size)
    assert str(image) == image._render_image(python_img, _ALPHA_THRESHOLD)


def test_format_spec():
    image = TermImage(python_img)

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
        " ",
    ):
        with pytest.raises(ValueError, match=r"Invalid format specification"):
            format(image, spec)

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
        "#123456",
        "#23af5b",
        "#abcdef",
        "#.4",
        "#.343545453453",
        "1.1#",
        "<.^#ffffff",
        "<1.^1#ffffff",
        f"<{columns}.^{lines}#ffffff",
    ):
        assert isinstance(format(image, spec), str)


def test_formatting():
    image = TermImage(python_img)
    check_formatting = image._check_formatting
    format_render = image._format_render

    # Argument valid types and values
    for value in (1, 1.0, (), []):
        with pytest.raises(TypeError, match="'h_align' must be .*"):
            check_formatting(h_align=value)
        with pytest.raises(TypeError, match="'v_align' must be .*"):
            check_formatting(v_align=value)

    for value in ("", "cool", ".", " ", "\n"):
        with pytest.raises(ValueError, match="Invalid horizontal .*"):
            check_formatting(h_align=value)
        with pytest.raises(ValueError, match="Invalid vertical .*"):
            check_formatting(v_align=value)

    for value in ("1", 1.0, (), []):
        with pytest.raises(TypeError, match="Padding width must be .*"):
            check_formatting(width=value)
        with pytest.raises(TypeError, match="Padding height must be .*"):
            check_formatting(height=value)

    for value in (0, -1, -100):
        with pytest.raises(ValueError, match="Padding width must be .*"):
            check_formatting(width=value)
        with pytest.raises(ValueError, match="Padding height must be .*"):
            check_formatting(height=value)

    # Padding width is validated
    with pytest.raises(ValueError, match="Padding width is larger .*"):
        check_formatting(width=columns + 1)  # Using default *h_allow*
    assert isinstance(check_formatting(width=columns), tuple)

    # recognizes allowance
    image.set_size(h_allow=2)
    with pytest.raises(ValueError, match="Padding width is larger .*"):
        check_formatting(width=columns - 1)  # Using last *h_allow*
    assert isinstance(check_formatting(width=columns - 2), tuple)

    image.size = None
    assert check_formatting() == (None,) * 4

    for value in "<|>":
        assert check_formatting(h_align=value) == (value, None, None, None)
    for val1, val2 in zip(("left", "center", "right"), "<|>"):
        assert check_formatting(h_align=val1) == (val2, None, None, None)

    for value in "^-_":
        assert check_formatting(v_align=value) == (None, None, value, None)
    for val1, val2 in zip(("top", "middle", "bottom"), "^-_"):
        assert check_formatting(v_align=val1) == (None, None, val2, None)

    # height goes beyond terminal height and allowance is not considered
    for value in (1, _size, lines, lines + 1):
        assert check_formatting(height=value) == (None, None, None, value)

    # width can not go beyond terminal width (minus allowance)
    for value in (1, _size, columns):
        assert check_formatting(width=value) == (None, value, None, None)

    size = _size - 5
    image.set_size(size)
    nlines = image.rendered_height

    render = str(image)
    assert format_render(render) == format(image)

    for width in range(size, columns + 1):
        assert format_render(render, "<", width).partition("\n")[0].count(" ") == width
        assert format_render(render, "|", width).partition("\n")[0].count(" ") == width
        assert format_render(render, ">", width).partition("\n")[0].count(" ") == width
        assert format_render(render, None, width).partition("\n")[0].count(" ") == width
    for height in range(nlines, lines + 1):
        assert format_render(render, None, None, "^", height).count("\n") + 1 == height
        assert format_render(render, None, None, "-", height).count("\n") + 1 == height
        assert format_render(render, None, None, "_", height).count("\n") + 1 == height
        assert format_render(render, None, None, None, height).count("\n") + 1 == height

    # Left + Up
    output = format_render(render, "<", columns, "^", lines)
    partition = output.partition("\033")[2]
    assert len(partition.partition("\n")[0].rpartition("m")[2]) == columns - size
    assert output.rpartition("m")[2].count("\n") == lines - nlines

    # Center + Middle
    output = format_render(render, "|", columns, "-", lines)
    left = (columns - size) // 2
    right = columns - size - left
    up = (lines - nlines) // 2
    down = lines - nlines - up
    partition = output.rpartition("m")[0]
    assert partition.rpartition("\n")[2].index("\033") == left
    assert output.partition("\033")[0].count("\n") == up
    partition = output.partition("\033")[2]
    assert len(partition.partition("\n")[0].rpartition("m")[2]) == right
    assert output.rpartition("m")[2].count("\n") == down

    # Right + Down
    output = format_render(render, ">", columns, "_", lines)
    partition = output.rpartition("m")[0]
    assert partition.rpartition("\n")[2].index("\033") == columns - size
    assert output.partition("\033")[0].count("\n") == lines - nlines

    image.scale = 0.5  # To ensure there's padding
    # First line in every render should be padding (except the terminal is so small)
    # No '\n' after the last line, hence the `+ 1` when counting lines

    # Allowance recognition

    # # Default allowances
    image.set_size()
    assert format(image).partition("\n")[0].count(" ") == columns
    assert format(image).count("\n") + 1 == lines - 2

    # # Vertical allowance nullified
    image.set_size(h_allow=2, v_allow=3, fit_to_width=True)
    assert format(image).partition("\n")[0].count(" ") == columns - 2
    assert format(image).count("\n") + 1 == lines

    # # Horizontal allowance nullified
    image.set_size(h_allow=2, v_allow=3, fit_to_height=True)
    assert format(image).partition("\n")[0].count(" ") == columns
    assert format(image).count("\n") + 1 == lines - 3

    # # `maxsize` nullifies allowances
    image.set_size(h_allow=2, v_allow=3, maxsize=(_size, _size))
    assert format(image).partition("\n")[0].count(" ") == columns
    assert format(image).count("\n") + 1 == lines


def test_iter():
    image = TermImage(python_img)
    with pytest.raises(ValueError, match="not animated"):
        iter(image)

    anim_image = TermImage(anim_img)
    image_it = iter(anim_image)
    assert isinstance(image_it, ImageIterator)
    assert image_it._image is anim_image


def test_draw():
    sys.stdout = stdout
    image = TermImage(python_img, width=_size)
    anim_image = TermImage(anim_img, width=_size)

    with pytest.raises(ValueError, match="Padding height .*"):
        anim_image.draw(pad_height=lines + 1)

    for value in (1, (), [], {}, b""):
        with pytest.raises(TypeError, match="'alpha' must be .*"):
            image.draw(alpha=value)

    for value in (-1.0, -0.1, 1.0, 1.1):
        with pytest.raises(ValueError, match="Alpha threshold .*"):
            image.draw(alpha=value)

    for value in ("f", "fffff", "fffffff", "12h45g", "-2343"):
        with pytest.raises(ValueError, match="Invalid hex color .*"):
            image.draw(alpha=value)

    # Non-animations

    # # Size validation

    image._size = (columns + 1, lines - 1)
    with pytest.raises(InvalidSize, match="image cannot .* terminal size"):
        image.draw()

    # # # Horizontal Allowance
    image.set_size(h_allow=2)
    image._size = (columns - 1, 1)
    with pytest.raises(InvalidSize, match="image cannot .* terminal size"):
        image.draw()

    # # # vertical Allowance
    image.set_size(v_allow=4)
    image._size = (1, lines - 3)
    with pytest.raises(InvalidSize, match="image cannot .* terminal size"):
        image.draw()

    # # `lines + 1` because *scroll* and *fit_to_width* nullify vertical allowance

    # # fit_to_width=True
    image.set_size(fit_to_width=True)
    image._size = (columns, lines + 1)
    image.draw()
    assert stdout.getvalue().count("\n") == lines + 1
    clear_stdout()

    # # scroll=True
    image.size = None
    image._size = (columns, lines + 1)
    image.draw(scroll=True)
    assert stdout.getvalue().count("\n") == lines + 1
    clear_stdout()

    # # check_size=False
    image.size = None
    image._size = (columns + 1, lines)
    image.draw(check_size=False)
    assert stdout.getvalue().count("\n") == lines
    clear_stdout()

    # # Animated image + animate=False

    # # # fit_to_width=True
    anim_image.set_size(fit_to_width=True)
    anim_image._size = (columns, lines + 1)
    anim_image.draw(animate=False)
    assert stdout.getvalue().count("\n") == lines + 1
    clear_stdout()

    # # # scroll=True
    anim_image.size = None
    anim_image._size = (columns, lines + 1)
    anim_image.draw(scroll=True, animate=False)
    assert stdout.getvalue().count("\n") == lines + 1
    clear_stdout()

    # # # check_size=False
    anim_image.size = None
    anim_image._size = (columns + 1, lines)
    anim_image.draw(animate=False, check_size=False)
    assert stdout.getvalue().count("\n") == lines
    clear_stdout()

    # Animations
    # `lines + 1` because *scroll* and *fit_to_width* nullify vertical allowance

    # # `fit_to_width=True` is overriden
    anim_image.set_size(fit_to_width=True)
    anim_image._size = (columns, lines + 1)
    with pytest.raises(InvalidSize, match="rendered height .* animations"):
        anim_image.draw()

    # # `scroll=True` is overriden
    anim_image.size = None
    anim_image._size = (columns, lines + 1)
    with pytest.raises(InvalidSize, match="rendered height .* animations"):
        anim_image.draw(scroll=True)

    # # Both of the above combined
    anim_image.set_size(fit_to_width=True)
    anim_image._size = (columns, lines + 1)
    with pytest.raises(InvalidSize, match="rendered height .* animations"):
        anim_image.draw(scroll=True)

    # # `check_size=False` is overriden
    anim_image.size = None
    anim_image._size = (columns + 1, lines)
    with pytest.raises(InvalidSize, match="animation cannot .* terminal size"):
        anim_image.draw(check_size=False)

    # # All of the above combined
    anim_image.set_size(fit_to_width=True)
    anim_image._size = (columns + 1, lines + 1)
    with pytest.raises(InvalidSize, match="animation cannot .* terminal size"):
        anim_image.draw(scroll=True, check_size=False)
