import atexit
from types import GeneratorType

import pytest
from PIL import Image

from term_image.exceptions import TermImageError
from term_image.image import BlockImage, ImageIterator, Size
from term_image.utils import COLOR_RESET

_size = (30, 15)

png_img = Image.open("tests/images/python.png")
png_image = BlockImage(png_img)
gif_img = Image.open("tests/images/lion.gif")
gif_image = BlockImage(gif_img)
webp_img = Image.open("tests/images/anim.webp")
webp_image = BlockImage(webp_img)

gif_image._size = _size
webp_image._size = _size


@atexit.register
def close_imgs():
    for img in (png_img, gif_img, webp_img):
        img.close()


def test_args():
    for value in ("tests/images/anim.webp", gif_img, webp_img):
        with pytest.raises(TypeError, match="'image'"):
            ImageIterator(value)
    with pytest.raises(ValueError, match="not animated"):
        ImageIterator(png_image)

    for value in (None, 2.0, 0.2, "2"):
        with pytest.raises(TypeError, match="'repeat'"):
            ImageIterator(gif_image, value)
    with pytest.raises(ValueError, match="'repeat'"):
        ImageIterator(gif_image, 0)

    for value in (None, 2.0, 2):
        with pytest.raises(TypeError, match="'format_spec'"):
            ImageIterator(gif_image, format_spec=value)
    with pytest.raises(ValueError, match="format specifier"):
        ImageIterator(gif_image, format_spec=".")

    for value in (None, 2.0, "2"):
        with pytest.raises(TypeError, match="'cached'"):
            ImageIterator(gif_image, cached=value)
    for value in (0, -1, -10):
        with pytest.raises(ValueError, match="'cached'"):
            ImageIterator(gif_image, cached=value)


class TestInit:
    def test_defaults(self):
        for image in (gif_image, webp_image):
            image_it = ImageIterator(image)
            assert image_it._image is image
            assert image_it._repeat == -1
            assert image_it._format == ""
            assert image_it._cached is (image.n_frames <= 100)
            assert isinstance(image_it._animator, GeneratorType)

    def test_with_args(self):
        for repeat, format_spec, cached in (
            (-1, "", 100),
            (2, "#", True),
            (10, "1.1", False),
            (100, "#.9", 1),
        ):
            image_it = ImageIterator(gif_image, repeat, format_spec, cached)
            assert image_it._image is gif_image
            assert image_it._repeat == repeat
            assert image_it._format == format_spec
            assert image_it._cached is (
                cached if isinstance(cached, bool) else gif_image.n_frames <= cached
            )
            assert isinstance(image_it._animator, GeneratorType)

    def test_no_caching_if_repeat_equals_1(self):
        for value in (True, 1, 100):
            image_it = ImageIterator(gif_image, 1, cached=value)
            assert image_it._cached is False

    def test_image_seek_position_unchanged(self):
        gif_image.seek(2)
        image_it = ImageIterator(gif_image)
        assert gif_image.tell() == 2

        next(image_it)
        assert gif_image.tell() == 0


def test_next():
    image_it = ImageIterator(gif_image, 1, "1.1")
    assert isinstance(next(image_it), str)

    for _ in range(gif_image.n_frames - 1):
        next(image_it)

    with pytest.raises(StopIteration):
        next(image_it)

    # Frame number is set to zero
    assert gif_image.tell() == 0

    # Iterator is closed
    assert not hasattr(image_it, "_animator")
    assert not hasattr(image_it, "_img")

    # All calls after StopIteration is first raised also raise StopIteration
    for _ in range(2):
        with pytest.raises(StopIteration):
            next(image_it)


def test_image_seek_has_no_effect():
    image_it = ImageIterator(gif_image, 1)
    next(image_it)
    assert gif_image.tell() == 0

    gif_image.seek(4)
    next(image_it)
    assert gif_image.tell() == 1


def test_iter():
    image_it = ImageIterator(gif_image, 1, "1.1")
    assert iter(image_it) is image_it

    # Image seek position is updated
    for n, _ in enumerate(ImageIterator(gif_image, 1, "1.1")):
        assert gif_image.tell() == n

    for image in (gif_image, webp_image):
        frames = tuple(ImageIterator(image, 1, "1.1"))
        assert len(frames) == image.n_frames
        assert all(isinstance(frame, str) for frame in frames)

        # Consecutive frames are different
        prev_frame = None
        for frame in frames:
            assert frame != prev_frame
            prev_frame = frame

    # Frames are the same as for manual iteration
    gif_image2 = BlockImage(gif_img)  # Need to change image size
    gif_image2._size = _size
    for n, frame in enumerate(ImageIterator(gif_image, 1, "1.1")):
        gif_image2.seek(n)
        assert frame == str(gif_image2)


def test_repeat():
    for image in (gif_image, webp_image):
        for value in (False, True):
            frames = tuple(ImageIterator(image, 2, "1.1", cached=value))

            # # Number of frames is multiplied
            assert len(frames) == image.n_frames * 2

            # # Corresponding frames in different repeat loops are the same
            assert frames[: image.n_frames] == frames[image.n_frames :]


def test_caching():
    def render(*args, **kwargs):
        nonlocal n_calls
        n_calls += 1
        if gif_image2.tell() == gif_image2.n_frames:
            raise EOFError
        return ""

    gif_image2 = BlockImage(gif_img)  # Need to change image size
    gif_image2._size = _size
    gif_image2._render_image = render

    n_calls = 0
    [*ImageIterator(gif_image2, 2, "1.1", cached=True)]
    assert n_calls == gif_image2.n_frames + 1  # +1 for EOF call

    n_calls = 0
    [*ImageIterator(gif_image2, 2, "1.1", cached=False)]
    assert n_calls == gif_image2.n_frames * 2 + 2  # +2 for EOF calls

    del gif_image2._render_image
    image_it = ImageIterator(gif_image2, 4, "1.1", cached=True)

    gif_image2._size = (20, 40)
    frame_0_1 = next(image_it)
    assert frame_0_1.count("\n") + 1 == 40
    image_it.seek(gif_image2.n_frames - 1)
    assert next(image_it).count("\n") + 1 == 40

    # Unchanged
    assert next(image_it) is frame_0_1
    image_it.seek(gif_image2.n_frames - 1)
    assert next(image_it).count("\n") + 1 == 40

    # Change in size
    gif_image2._size = (40, 20)
    frame_0_2 = next(image_it)
    assert frame_0_2 is not frame_0_1
    assert frame_0_2.count("\n") + 1 == 20
    image_it.seek(gif_image2.n_frames - 1)
    assert next(image_it).count("\n") + 1 == 20

    # Change in scale
    gif_image2.scale = 0.5
    frame_0_3 = next(image_it)
    assert frame_0_3 is not frame_0_1
    assert frame_0_3 is not frame_0_2
    assert frame_0_3.count("\n") + 1 == 10
    image_it.seek(gif_image2.n_frames - 1)
    assert next(image_it).count("\n") + 1 == 10

    image_it.close()


def test_sizing():
    def test(image_it):
        for value in Size:
            gif_image2.size = value
            assert next(image_it).count("\n") + 1 == gif_image2.rendered_height
            assert gif_image2.size is value

        gif_image2._size = (40, 20)
        assert next(image_it).count("\n") + 1 == 20
        assert gif_image2._size == (40, 20)

        gif_image2._size = (20, 10)
        assert next(image_it).count("\n") + 1 == 10
        assert gif_image2._size == (20, 10)

        gif_image2.size = Size.FIT
        next(image_it)
        assert gif_image2.size is Size.FIT

    gif_image2 = BlockImage(gif_img)  # Need to change image size

    # Uncached loop
    image_it = ImageIterator(gif_image2, 1, "1.1")
    test(image_it)

    # Cached loop
    image_it = ImageIterator(gif_image2, 2, "1.1", True)
    for _ in range(gif_image2.n_frames):
        next(image_it)
    test(image_it)


def test_formatting():
    # Transparency enabled, not padded
    image_it = ImageIterator(gif_image, 1, "1.1")
    assert next(image_it).count("\n") + 1 == _size[1]
    # First line without escape codes
    assert next(image_it).partition("\n")[0].strip(COLOR_RESET) == " " * _size[0]

    # Transparency disabled, not padded
    image_it = ImageIterator(gif_image, 1, "1.1#")
    assert next(image_it).count("\n") + 1 == _size[1]
    # First line without escape codes
    assert next(image_it).partition("\n")[0].strip(COLOR_RESET) != " " * _size[0]

    # Transparency disabled, padded
    image_it = ImageIterator(gif_image, 1, f"{_size[0] + 2}.{_size[1] + 2}#")
    assert next(image_it).count("\n") + 1 == _size[1] + 2
    # First line should be padding, so no escape codes
    assert next(image_it).partition("\n")[0] == " " * (_size[0] + 2)


def test_loop_no():
    for cached in (False, True):
        image_it = ImageIterator(gif_image, 2, cached=cached)
        assert image_it.loop_no is None

        next(image_it)
        assert image_it.loop_no == 2
        for _ in range(gif_image.n_frames - 1):
            next(image_it)
        assert image_it.loop_no == 2

        next(image_it)
        assert image_it.loop_no == 1
        for _ in range(gif_image.n_frames - 1):
            next(image_it)
        assert image_it.loop_no == 1

        with pytest.raises(StopIteration):
            next(image_it)
        assert image_it.loop_no == 0


def test_close():
    # From PIL image-sourced image
    image_it = ImageIterator(gif_image, 1)
    next(image_it)
    img = image_it._img
    assert img is gif_img

    image_it.close()
    assert gif_image.tell() == 0
    assert not hasattr(image_it, "_animator")
    assert not hasattr(image_it, "_img")
    assert img.load()

    # File-sourced image
    image_it = ImageIterator(BlockImage.from_file(gif_image._source.filename), 1)
    next(image_it)
    img = image_it._img
    image_it.close()
    assert gif_image.tell() == 0
    assert not hasattr(image_it, "_animator")
    assert not hasattr(image_it, "_img")
    with pytest.raises(ValueError, match="Operation on closed image"):
        img.load()


class TestSeek:
    def test_seek_args(self):
        image_it = ImageIterator(gif_image)

        for value in (1.0, "1", [], ()):
            with pytest.raises(TypeError):
                image_it.seek(value)

        for value in (-2, -1, gif_image.n_frames, gif_image.n_frames + 1):
            with pytest.raises(ValueError):
                image_it.seek(value)

        with pytest.raises(TermImageError):
            image_it.seek(1)

    def test_seek(self):
        for cached in (False, True):
            image_it = ImageIterator(gif_image, 2, cached=cached)
            frame_0 = next(image_it)
            for _ in range(5):
                next(image_it)
            frame_6 = next(image_it)

            # Image seek position is always the number of the last yielded frame. Hence:
            # - must remain unchanged after `seek()`.
            # - must equal the seek-ed position after the `next()` immediately following
            # `seek()`.

            # 1st loop

            image_it.seek(0)
            assert image_it._loop_no == 2
            assert gif_image.tell() == 6
            assert frame_0 == next(image_it)
            assert image_it._loop_no == 2
            assert gif_image.tell() == 0

            image_it.seek(6)
            assert image_it._loop_no == 2
            assert gif_image.tell() == 0
            assert frame_6 == next(image_it)
            assert image_it._loop_no == 2
            assert gif_image.tell() == 6

            image_it.seek(gif_image.n_frames - 1)
            assert image_it._loop_no == 2
            assert gif_image.tell() == 6
            next(image_it)
            assert image_it._loop_no == 2
            assert gif_image.tell() == gif_image.n_frames - 1

            # 2nd loop (cached when `cached=True`)

            assert frame_0 == next(image_it)
            assert image_it._loop_no == 1
            assert gif_image.tell() == 0

            image_it.seek(6)
            assert image_it._loop_no == 1
            assert gif_image.tell() == 0
            assert frame_6 == next(image_it)
            assert image_it._loop_no == 1
            assert gif_image.tell() == 6

            image_it.seek(0)
            assert image_it._loop_no == 1
            assert gif_image.tell() == 6
            assert frame_0 == next(image_it)
            assert image_it._loop_no == 1
            assert gif_image.tell() == 0

            image_it.seek(gif_image.n_frames - 1)
            assert image_it._loop_no == 1
            assert gif_image.tell() == 0
            next(image_it)
            assert image_it._loop_no == 1
            assert gif_image.tell() == gif_image.n_frames - 1

            # Iteration ends normally
            with pytest.raises(StopIteration):
                next(image_it)

            # After closing
            with pytest.raises(TermImageError):
                image_it.seek(0)

    def test_seek_skipped_frames_caching(self):
        image_it = ImageIterator(gif_image, 1)
        next(image_it)
        frame_1 = next(image_it)
        for _ in range(4):
            next(image_it)
        frame_6 = next(image_it)

        image_it = ImageIterator(gif_image, 2, cached=True)
        next(image_it)
        image_it.seek(gif_image.n_frames - 1)
        next(image_it) and next(image_it)
        cache = image_it._animator.gi_frame.f_locals["cache"]

        assert frame_1 == next(image_it) is cache[1][0]
        image_it.seek(6)
        assert frame_6 == next(image_it) is cache[6][0]
