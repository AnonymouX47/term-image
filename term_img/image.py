"""
Core Library Definitions
========================
"""

__all__ = ("TermImage",)

import io
import os
import re
import requests
import time
from itertools import cycle
from math import ceil
from operator import gt, mul, sub, truediv
from random import randint
from shutil import get_terminal_size

from PIL import Image, UnidentifiedImageError
from typing import Any, Optional, Tuple, Union
from types import FunctionType
from urllib.parse import urlparse

from .exceptions import InvalidSize, TermImageException, URLNotFoundError


_ALPHA_THRESHOLD = 40 / 255  # Default alpha threshold
_FG_FMT: str = "\033[38;2;%d;%d;%dm"
_BG_FMT: str = "\033[48;2;%d;%d;%dm"
_UPPER_PIXEL: str = "\u2580"  # upper-half block element
_LOWER_PIXEL: str = "\u2584"  # lower-half block element
_FORMAT_SPEC = re.compile(
    r"(([<|>])?(\d+)?)?(\.([-^_])?(\d+)?)?(#(\.\d+|[0-9a-f]{6})?)?",
    re.ASCII,
)
_HEX_COLOR_FORMAT = re.compile("#[0-9a-f]{6}", re.ASCII)


class TermImage:
    """Text-printable image

    Args:
        image: Image to be rendered.
        width: The width to render the image with.
        height: The height to render the image with.
        scale: The image render scale on respective axes.

    NOTE:
        * *width* is not neccesarily the exact number of columns that'll be used
          to render the image. That is influenced by the currently set font ratio.
        * *height* is **2 times** the number of lines that'll be used on the terminal.
        * If neither is given or ``None``, the size is automatically determined
          when the image is to be rendered, such that it can fit within the terminal.
        * The size is multiplied by the scale on each axis respectively before the image
          is rendered.
    """

    # Special Methods

    def __init__(
        self,
        image: Image.Image,
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        scale: Tuple[float, float] = (1.0, 1.0),
    ):
        """See class description"""
        if not isinstance(image, Image.Image):
            raise TypeError(
                "Expected a 'PIL.Image.Image' instance for 'image' "
                f"(got: {type(image).__name__!r})."
            )

        self._closed = False
        self._source = image
        self._buffer = io.StringIO()
        self._original_size = image.size
        self._size = (
            None if width is None is height else self._valid_size(width, height)
        )
        self._scale = []
        self._scale[:] = self.__check_scale(scale)

        self._is_animated = hasattr(image, "is_animated") and image.is_animated
        if self._is_animated:
            self._frame_duration = 0.1
            self._seek_position = 0
            self._n_frames = image.n_frames

        # Recognized advanced sizing options.
        # These are initialized here only to avoid `AttributeError`s in case `_size` is
        # initially set via a means other than `set_size()`.
        self.__check_height = True
        self.__h_allow = 0
        self.__v_allow = 2  # A 2-line allowance for the shell prompt, etc

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, typ, val, tb):
        self.close()
        return False  # Currently, no particular exception is suppressed

    def __format__(self, spec):
        """Renders the image with alignment, padding and transparency control"""
        # Only the currently set frame is rendered for animated images
        match_ = _FORMAT_SPEC.fullmatch(spec)
        if not match_:
            raise ValueError("Invalid format specifier")

        _, h_align, width, _, v_align, height, alpha, threshold_or_bg = match_.groups()

        width = width and int(width)
        height = height and int(height)

        return self._renderer(
            lambda image: self.__format_render(
                self._render_image(
                    image,
                    (
                        threshold_or_bg
                        and (
                            "#" + threshold_or_bg
                            if _HEX_COLOR_FORMAT.fullmatch("#" + threshold_or_bg)
                            else float(threshold_or_bg)
                        )
                        if alpha
                        else _ALPHA_THRESHOLD
                    ),
                ),
                *self.__check_formating(h_align, width, v_align, height),
            )
        )

    def __repr__(self):
        return (
            "<{}(source={!r}, original_size={}, size={}, scale={}, is_animated={})>"
        ).format(
            type(self).__name__,
            (
                self.__url
                if hasattr(self, f"_{__class__.__name__}__url")
                else self._source
            ),
            self._original_size,
            self._size,
            self.scale,  # Stored as a list but should be shown as a tuple
            self._is_animated,
        )

    def __str__(self):
        """Renders the image with transparency enabled and without alignment"""
        # Only the currently set frame is rendered for animated images
        return self._renderer(lambda image: self._render_image(image, _ALPHA_THRESHOLD))

    # Properties

    closed = property(
        lambda self: self._closed,
        doc="Instance finalization status",
    )

    frame_duration = property(
        lambda self: self._frame_duration if self._is_animated else None,
        doc="Duration (in seconds) of a single frame for animated images",
    )

    @frame_duration.setter
    def frame_duration(self, value: float) -> None:
        if not isinstance(value, float):
            raise TypeError(f"Invalid duration type (got: {type(value).__name__})")
        if value <= 0:
            raise ValueError(
                f"Invalid frame duration (got: {value}, n_frames={self._n_frames})"
            )
        if self._is_animated:
            self._frame_duration = value

    height = property(
        lambda self: self._size and self._size[1],
        lambda self, height: self.set_size(height=height),
        doc="""
        Image render height

        ``None`` when render size is unset.

        Settable values:

            * ``None``: Sets the render size to the automatically calculated one.
            * A positive ``int``: Sets the render height to the given value and
              the width proprtionally.

        The image is actually rendered using half this number of lines
        """,
    )

    is_animated = property(
        lambda self: self._is_animated,
        doc="``True`` if the image is animated. Otherwise, ``False``.",
    )

    original_size = property(
        lambda self: self._original_size, doc="Original image size"
    )

    n_frames = property(
        lambda self: self._n_frames if self._is_animated else 1,
        doc="The number of frames in the image",
    )

    rendered_height = property(
        lambda self: ceil(
            (self._size or self._valid_size(None, None))[1] * self._scale[1] / 2
        ),
        doc="The number of lines that the rendered image will occupy on the terminal",
    )

    @property
    def rendered_size(self) -> Tuple[int, int]:
        """The number of columns and lines (respectively) that the rendered image will
        occupy in the terminal
        """
        columns, rows = map(
            round,
            map(
                mul,
                self._size or self._valid_size(None, None),
                map(truediv, self._scale, (_pixel_ratio, 1)),
            ),
        )
        return (columns, ceil(rows / 2))

    rendered_width = property(
        lambda self: round(
            (self._size or self._valid_size(None, None))[0]
            * self._scale[0]
            / _pixel_ratio
        ),
        doc="The number of columns that the rendered image will occupy on the terminal",
    )

    scale = property(
        lambda self: tuple(self._scale),
        doc="""
        Image render scale

        Settable values are:

            * A *scale value*; sets both axes.
            * A ``tuple`` of two *scale values*; sets ``(x, y)`` respectively.

        A scale value is a ``float`` in the range **0.0 < value <= 1.0**.
        """,
    )

    @scale.setter
    def scale(self, scale: Union[float, Tuple[float, float]]) -> None:
        if isinstance(scale, float):
            if not 0.0 < scale <= 1.0:
                raise ValueError(f"Scale value out of range (got: {scale})")
            self._scale[:] = (scale,) * 2
        elif isinstance(scale, tuple):
            self._scale[:] = self.__check_scale(scale)
        else:
            raise TypeError("Given value must be a float or a tuple of floats")

    scale_x = property(
        lambda self: self._scale[0],
        doc="""
        x-axis render scale

        A scale value is a ``float`` in the range **0.0 < x <= 1.0**.
        """,
    )

    @scale_x.setter
    def scale_x(self, x: float) -> None:
        self._scale[0] = self.__check_scale_2(x)

    scale_y = property(
        lambda self: self._scale[1],
        doc="""
        y-ayis render scale

        A scale value is a ``float`` in the range **0.0 < y <= 1.0**.
        """,
    )

    @scale_y.setter
    def scale_y(self, y: float) -> None:
        self._scale[1] = self.__check_scale_2(y)

    size = property(
        lambda self: self._size,
        doc="""Image render size

        ``None`` when render size is unset.

        Setting this to ``None`` unsets the *render size* (so that it's automatically
        calculated whenever the image is rendered) and resets the recognized advanced
        sizing options to their defaults.
        """,
    )

    @size.setter
    def size(self, value: None) -> None:
        if value is not None:
            raise TypeError("The only acceptable value is `None`")
        self._size = value
        self.__check_height = True
        self.__h_allow = 0
        self.__v_allow = 2  # A 2-line allowance for the shell prompt, etc

    source = property(
        lambda self: (
            self.__url if hasattr(self, f"_{__class__.__name__}__url") else self._source
        ),
        doc="""
        The source from which the instance was initialized

        Can be a PIL image, file path or URL.
        """,
    )

    width = property(
        lambda self: self._size and self._size[0],
        lambda self, width: self.set_size(width),
        doc="""
        Image render width

        ``None`` when render size is unset.

        Settable values:

            * ``None``: Sets the render size to the automatically calculated one.
            * A positive ``int``: Sets the render width to the given value and
              the height proportionally.
        """,
    )

    # Public Methods

    def close(self) -> None:
        """Finalizes the instance and releases external resources.

        NOTE:
            * It's not neccesary to explicity call this method, as it's automatically
              called when neccesary.
            * This method can be safely called mutiple times.
            * If the instance was initialized with a PIL image, it's never finalized.
        """
        try:
            if not self._closed:
                self._buffer.close()
                self._buffer = None

                if (
                    hasattr(self, f"_{__class__.__name__}__url")
                    and os.path.exists(self._source)
                    # The file might not exist for whatever reason.
                ):
                    os.remove(self._source)
        except AttributeError:
            # Instance creation or initialization was unsuccessful
            pass
        finally:
            self._closed = True

    def draw_image(
        self,
        h_align: str = "center",
        pad_width: Optional[int] = None,
        v_align: str = "middle",
        pad_height: Optional[int] = None,
        alpha: Optional[float] = _ALPHA_THRESHOLD,
        *,
        ignore_oversize: bool = False,
    ) -> None:
        """Draws/Displays an image in the terminal, with optional alignment and padding.

        Args:
            h_align: Horizontal alignment ("left", "center" or "right").
            pad_width: Number of columns within which to align the image.

              * Excess columns are filled with spaces.
              * default: terminal width.

            v_align: Vertical alignment ("top", "middle" or "bottom").
            pad_height: Number of lines within which to align the image.

              * Excess lines are filled with spaces.
              * default: terminal height, with a 2-line allowance.

            alpha: Transparency setting.

              * If ``None``, transparency is disabled (i.e black background).
              * If a ``float`` (**0.0 <= x < 1.0**), specifies the alpha ratio
                **above** which pixels are taken as *opaque*.
              * If a string, specifies a **hex color** with which transparent background
                should be replaced.

            ignore_oversize: If ``True``, do not verify if the image will fit into
              the terminal with it's currently set render size.

        Raises:
            term_img.exceptions.InvalidSize: The terminal has been resized in such a
              way that the previously set size can no longer fit into it.
            term_img.exceptions.InvalidSize: The image is **animated** and the
              previously set size won't fit into the terminal.
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument has an unexpected/invalid value.
            ValueError: Render size or scale too small.

        NOTE:
            * Animated images are displayed infinitely but can be terminated with
              ``Ctrl-C``.
            * If the ``set_size()`` method was previously used to set the *render size*,
              (directly or not), the last values of its *check_height*, *h_allow* and
              *v_allow* parameters are taken into consideration, with *check_height*
              applying to only non-animated images.
            * For animated images:

              * *Render size* and *padding height* are always validated.
              * *ignore_oversize* has no effect.
        """
        h_align, pad_width, v_align, pad_height = self.__check_formating(
            h_align, pad_width, v_align, pad_height
        )

        if (
            self._is_animated
            and None is not pad_height > get_terminal_size()[1] - self.__v_allow
        ):
            raise ValueError(
                "Padding height must not be greater than the terminal height "
                "for animated images"
            )

        if alpha is not None:
            if isinstance(alpha, float):
                if not 0.0 <= alpha < 1.0:
                    raise ValueError(f"Alpha threshold out of range (got: {alpha})")
            elif isinstance(alpha, str):
                if not _HEX_COLOR_FORMAT.fullmatch(alpha):
                    raise ValueError(f"Invalid hex color string (got: {alpha})")
            else:
                raise TypeError(
                    "'alpha' must be `None` or of type `float` or `str` "
                    f"(got: {type(alpha).__name__})"
                )

        def render(image) -> None:
            try:
                if self._is_animated:
                    self.__display_animated(
                        image, alpha, h_align, pad_width, v_align, pad_height
                    )
                else:
                    print(
                        self.__format_render(
                            self._render_image(image, alpha),
                            h_align,
                            pad_width,
                            v_align,
                            pad_height,
                        ),
                        end="",
                        flush=True,
                    )
            finally:
                print("\033[0m")  # Always reset color

        self._renderer(render, self._is_animated or not ignore_oversize)

    @classmethod
    def from_file(
        cls,
        filepath: str,
        **kwargs,
    ) -> "TermImage":
        """Creates a ``TermImage`` instance from an image file.

        Args:
            filepath: Relative/Absolute path to an image file.
            kwargs: Same keyword arguments as the class constructor.

        Returns:
            A new ``TermImage`` instance.

        Raises:
            TypeError: *filepath* is not a string.
            FileNotFoundError: The given path does not exist.
            IsADirectoryError: Propagated from from ``PIL.Image.open()``.
            UnidentifiedImageError: Propagated from from ``PIL.Image.open()``.
        """
        if not isinstance(filepath, str):
            raise TypeError(
                f"File path must be a string (got: {type(filepath).__name__!r})."
            )

        # Intentionally propagates `UnidentifiedImageError` and `IsADirectoryError`
        # since the messages are OK.
        try:
            Image.open(filepath)
        except FileNotFoundError:
            raise FileNotFoundError(f"No such file: {filepath!r}") from None

        new = cls(Image.open(filepath), **kwargs)
        new._source = os.path.realpath(filepath)
        return new

    @classmethod
    def from_url(
        cls,
        url: str,
        **kwargs,
    ) -> "TermImage":
        """Creates a ``TermImage`` instance from an image URL.

        Args:
            url: URL of an image file.
            kwargs: Same keyword arguments as the class constructor.

        Returns:
            A new ``TermImage`` instance.

        Raises:
            TypeError: *url* is not a string.
            ValueError: The URL is invalid.
            term_img.exceptions.URLNotFoundError: The URL does not exist.
            UnidentifiedImageError: Propagated from ``PIL.Image.open()``.

        Also propagates connection-related errors from ``requests.get()``.
        """
        if not isinstance(url, str):
            raise TypeError(f"URL must be a string (got: {type(url).__name__!r}).")
        if not all(urlparse(url)[:3]):
            raise ValueError(f"Invalid url: {url!r}")

        # Propagates connection-related errors.
        response = requests.get(url, stream=True)
        if response.status_code == 404:
            raise URLNotFoundError(f"URL {url!r} does not exist.")
        try:
            Image.open(io.BytesIO(response.content))
        except UnidentifiedImageError as e:
            e.args = (f"The URL {url!r} doesn't link to a identifiable image.",)
            raise e from None

        basedir = os.path.join(os.path.expanduser("~"), ".term_img", "temp")
        if not os.path.isdir(basedir):
            os.mkdir(basedir)

        filepath = os.path.join(basedir, os.path.basename(urlparse(url).path))
        while os.path.exists(filepath):
            filepath += str(randint(0, 9))
        with open(filepath, "wb") as image_writer:
            image_writer.write(response.content)

        new = cls(Image.open(filepath), **kwargs)
        new._source = filepath
        new.__url = url
        return new

    def seek(self, pos: int) -> None:
        """Changes current image frame.

        Frame numbers start from 0 (zero).
        """
        if not isinstance(pos, int):
            raise TypeError(f"Invalid seek position type (got: {type(pos).__name__})")
        if not 0 <= pos < self._n_frames if self._is_animated else pos:
            raise ValueError(
                f"Invalid frame number (got: {pos}, n_frames={self.n_frames})"
            )
        if self._is_animated:
            self._seek_position = pos

    def set_size(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        h_allow: int = 0,
        v_allow: int = 2,
        *,
        maxsize: Optional[Tuple[int, int]] = None,
        check_width: bool = True,
        check_height: bool = True,
    ) -> None:
        """Sets the *render size* with advanced control.

        Args:
            width: Render width to use.
            height: Render height to use.
            h_allow: Horizontal allowance i.e minimum number of columns to leave unused.
            v_allow: Vertical allowance i.e minimum number of lines to leave unused.
            maxsize: If given, it's used instead of the terminal size.
            check_width: If ``False``, the validity of the resulting *rendered width*
              is not checked.
            check_height: If ``False``, the validity of the resulting *rendered height*
              is not checked.

        Raises:
            term_img.exceptions.InvalidSize: The terminal size is too small.
            term_img.exceptions.InvalidSize: The resulting *rendered size* will not
              fit into the terminal or *maxsize*.
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument has an unexpected/invalid value but of an
              appropriate type.
            ValueError: Both *width* and *height* are specified.

        If neither *width* nor *height* is given or anyone given is ``None``:

          * and *check_height* is ``True``, the size is automatically calculated to fit
            within the terminal size (or *maxsize*, if given).
          * and *check_height* is ``False``, the size is set such that the
            *rendered width* is exactly the terminal width (or ``maxsize[1]``)
            (assuming the *render scale* equals 1), regardless of the font ratio.

        | Allowance does not apply when *maxsize* is given.
        | Vertical allowance has no effect when *check_height* is ``False``.

        The *check_height* might be set to ``False`` to set the *render size* for
        vertically-oriented images (i.e images with height > width) such that the
        drawn image spans more columns but the terminal window has to be scrolled
        to view the entire image.

        All image rendering and formatting methods recognize and respect the
        *check_height*, *h_allow* and *v_allow* options, until the size is re-set
        or unset.

        *check_width* is only provided for completeness and is meant for advanced use.
        It should probably be used only when the image will not be drawn to the
        current terminal.
        """
        if width is not None is not height:
            raise ValueError("Cannot specify both width and height")
        for argname, x in zip(("width", "height"), (width, height)):
            if not (x is None or isinstance(x, int)):
                raise TypeError(
                    f"{argname} must be `None` or an integer "
                    f"(got: type {type(x).__name__!r})"
                )
            if None is not x <= 0:
                raise ValueError(f"{argname} must be positive (got: {x})")
        for argname, x in zip(("h_allow", "v_allow"), (h_allow, v_allow)):
            if not isinstance(x, int):
                raise TypeError(
                    f"{argname} must be an integer (got: type {type(x).__name__!r})"
                )
            if x < 0:
                raise ValueError(f"{argname} must be non-negative (got: {x})")
        if maxsize is not None:
            if not (
                isinstance(maxsize, tuple) and all(isinstance(x, int) for x in maxsize)
            ):
                raise TypeError(
                    f"'maxsize' must be a tuple of `int`s (got: {maxsize!r})"
                )

            if not (len(maxsize) == 2 and all(x > 0 for x in maxsize)):
                raise ValueError(
                    f"'maxsize' must contain two positive integers (got: {maxsize})"
                )
        if not (isinstance(check_width, bool) and (check_height, bool)):
            raise TypeError("The size-Check arguments must be booleans")

        self._size = self._valid_size(
            width,
            height,
            h_allow,
            v_allow * check_height,
            maxsize=maxsize,
            check_height=check_height,
            ignore_oversize=not (check_width or check_height),
        )
        self.__check_height = check_height
        self.__h_allow = h_allow * (not maxsize)
        self.__v_allow = v_allow * (not maxsize) * check_height

    def tell(self) -> int:
        """Returns the current image frame number"""
        return self._seek_position if self._is_animated else 0

    # Private Methods

    def __check_formating(
        self,
        h_align: Optional[str] = None,
        width: Optional[int] = None,
        v_align: Optional[str] = None,
        height: Optional[int] = None,
    ) -> Tuple[Union[None, str, int]]:
        """Validates formatting arguments while also translating literal ones.

        Returns:
            The respective arguments appropriate for ``__format_render()``.
        """
        if h_align is not None:
            align = {"left": "<", "center": "|", "right": ">"}.get(h_align, h_align)
            if not align:
                raise ValueError(f"Invalid horizontal alignment option: {h_align!r}")
            h_align = align

        if not isinstance(width, (type(None), int)):
            raise TypeError("Wrong type; Padding width must be None or an integer.")
        if width is not None:
            if width <= 0:
                raise ValueError(f"Padding width must be positive (got: {width})")
            if width > get_terminal_size()[0] - self.__h_allow:
                raise ValueError("Padding width larger than terminal width")

        if v_align is not None:
            align = {"top": "^", "middle": "-", "bottom": "_"}.get(v_align, v_align)
            if not align:
                raise ValueError(f"Invalid vertical alignment option: {v_align!r}")
            v_align = align

        if not isinstance(height, (type(None), int)):
            raise TypeError("Wrong type; Padding height must be None or an integer.")
        if None is not height <= 0:
            raise ValueError(f"Padding height must be positive (got: {height})")

        return h_align, width, v_align, height

    @staticmethod
    def __check_scale(scale: Tuple[float, float]) -> Tuple[float, float]:
        """Checks a tuple of scale values.

        Returns:
            The tuple of scale values, if valid.

        Raises:
            TypeError: The object is not a tuple of ``float``\\ s.
            ValueError: The object is not a 2-tuple or the values are out of range.
        """
        if not (isinstance(scale, tuple) and all(isinstance(x, float) for x in scale)):
            raise TypeError(f"'scale' must be a tuple of floats (got: {scale!r})")

        if not (len(scale) == 2 and all(0.0 < x <= 1.0 for x in scale)):
            raise ValueError(
                f"'scale' must be a tuple of two floats, 0.0 < x <= 1.0 (got: {scale})"
            )
        return scale

    @staticmethod
    def __check_scale_2(value: float) -> float:
        """Checks a single scale value.

        Returns:
            The scale value, if valid.

        Raises:
            TypeError: The object is not a ``float``.
            ValueError: The value is out of range.
        """
        if not isinstance(value, float):
            raise TypeError(
                f"Given value must be a float (got: type {type(value).__name__!r})"
            )
        if not 0.0 < value <= 1.0:
            raise ValueError(f"Scale value out of range (got: {value})")
        return value

    def __display_animated(
        self, image: Image.Image, alpha: Optional[float], *fmt: Union[None, str, int]
    ) -> None:
        """Displays an animated GIF image in the terminal.

        This is done infinitely but can be terminated with ``Ctrl-C``.
        """
        lines = max(
            (fmt or (None,))[-1] or get_terminal_size()[1] - self.__v_allow,
            self.rendered_height,
        )
        cache = [None] * self._n_frames
        prev_seek_pos = self._seek_position
        try:
            # By implication, the first frame is repeated once at the start :D
            self.seek(0)
            cache[0] = frame = self.__format_render(
                self._render_image(image, alpha), *fmt
            )
            duration = self._frame_duration
            for n in cycle(range(self._n_frames)):
                print(frame)  # Current frame

                # Render next frame during current frame's duration
                start = time.time()
                self._buffer.truncate()  # Clear buffer
                self.seek(n)
                if cache[n]:
                    frame = cache[n]
                else:
                    cache[n] = frame = self.__format_render(
                        self._render_image(image, alpha),
                        *fmt,
                    )
                # Move cursor up to the first line of the image
                # Not flushed until the next frame is printed
                print("\033[%dA" % lines, end="")

                # Left-over of current frame's duration
                time.sleep(max(0, duration - (time.time() - start)))
        finally:
            self.seek(prev_seek_pos)
            # Move the cursor to the line after the image
            # Prevents "overlayed" output on the terminal
            print("\033[%dB" % lines, end="", flush=True)

    def __format_render(
        self,
        render: str,
        h_align: Optional[str] = None,
        width: Optional[int] = None,
        v_align: Optional[str] = None,
        height: Optional[int] = None,
    ) -> str:
        """Formats rendered image text.

        All arguments should be passed through ``__check_formatting()`` first.
        """
        lines = render.splitlines()
        cols, rows = self.rendered_size

        width = width or get_terminal_size()[0] - self.__h_allow
        width = max(cols, width)
        if h_align == "<":  # left
            pad_left = ""
            pad_right = " " * (width - cols)
        elif h_align == ">":  # right
            pad_left = " " * (width - cols)
            pad_right = ""
        else:  # center
            pad_left = " " * ((width - cols) // 2)
            pad_right = " " * (width - cols - len(pad_left))

        if pad_left and pad_right:
            lines = [pad_left + line + pad_right for line in lines]
        elif pad_left:
            lines = [pad_left + line for line in lines]
        elif pad_right:
            lines = [line + pad_right for line in lines]

        height = height or get_terminal_size()[1] - self.__v_allow
        height = max(rows, height)
        if v_align == "^":  # top
            pad_up = 0
            pad_down = height - rows
        elif v_align == "_":  # bottom
            pad_up = height - rows
            pad_down = 0
        else:  # middle
            pad_up = (height - rows) // 2
            pad_down = height - rows - pad_up

        if pad_down:
            lines[rows:] = (" " * width,) * pad_down
        if pad_up:
            lines[:0] = (" " * width,) * pad_up

        return "\n".join(lines)

    def _render_image(self, image: Image.Image, alpha: Optional[float]) -> str:
        """Converts image pixel data into a "color-coded" string.

        Two pixels per character using FG and BG colors.
        """
        if self._closed:
            raise TermImageException("This image has been finalized")

        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        # Eliminate attribute resolution cost
        buffer = self._buffer
        buf_write = buffer.write

        def update_buffer():
            if alpha:
                no_alpha = False
                if a_cluster1 == 0 == a_cluster2:
                    buf_write("\033[0m")
                    buf_write(" " * n)
                elif a_cluster1 == 0:  # up is transparent
                    buf_write("\033[0m")
                    buf_write(_FG_FMT % cluster2)
                    buf_write(_LOWER_PIXEL * n)
                elif a_cluster2 == 0:  # down is transparent
                    buf_write("\033[0m")
                    buf_write(_FG_FMT % cluster1)
                    buf_write(_UPPER_PIXEL * n)
                else:
                    no_alpha = True

            if not alpha or no_alpha:
                buf_write(_BG_FMT % cluster2)
                if cluster1 == cluster2:
                    buf_write(" " * n)
                else:
                    buf_write(_FG_FMT % cluster1)
                    buf_write(_UPPER_PIXEL * n)

        if self._is_animated:
            image.seek(self._seek_position)
        width, height = map(
            round, map(mul, self._size, map(truediv, self._scale, (_pixel_ratio, 1)))
        )
        try:
            image = image.convert("RGBA").resize((width, height))
        except ValueError:
            raise ValueError("Render size or scale too small")
        if isinstance(alpha, str):
            bg = Image.new("RGBA", image.size, alpha)
            bg.alpha_composite(image)
            if not isinstance(self._source, Image.Image):
                image.close()
            image = bg
            alpha = None
        rgb = tuple(image.convert("RGB").getdata())
        alpha_threshold = round((alpha or 0) * 255)
        alpha_ = [0 if a < alpha_threshold else a for a in image.getdata(3)]

        # To distinguish 0.0 from None, since _alpha_ is used via "truth value testing"
        if alpha == 0.0:
            alpha = 0.1

        # clean up
        if not isinstance(self._source, Image.Image):
            image.close()

        if height % 2:
            # Starting index of the last row, when height is odd
            mark = width * (height // 2) * 2
            rgb, last_rgb = rgb[:mark], rgb[mark:]
            alpha_, last_alpha = alpha_[:mark], alpha_[mark:]

        rgb_pairs = (
            (
                zip(rgb[x : x + width], rgb[x + width : x + width * 2]),
                (rgb[x], rgb[x + width]),
            )
            for x in range(0, len(rgb), width * 2)
        )
        a_pairs = (
            (
                zip(alpha_[x : x + width], alpha_[x + width : x + width * 2]),
                (alpha_[x], alpha_[x + width]),
            )
            for x in range(0, len(alpha_), width * 2)
        )

        row_no = 0
        # Two rows of pixels per line
        for (rgb_pair, (cluster1, cluster2)), (a_pair, (a_cluster1, a_cluster2)) in zip(
            rgb_pairs, a_pairs
        ):
            row_no += 2
            n = 0
            for (p1, p2), (a1, a2) in zip(rgb_pair, a_pair):
                # Color-code characters and write to buffer
                # when upper and/or lower pixel color/alpha-level changes
                if not (alpha and a1 == a_cluster1 == 0 == a_cluster2 == a2) and (
                    p1 != cluster1
                    or p2 != cluster2
                    or alpha
                    and (
                        # From non-transparent to transparent
                        a_cluster1 != a1 == 0
                        or a_cluster2 != a2 == 0
                        # From transparent to non-transparent
                        or 0 == a_cluster1 != a1
                        or 0 == a_cluster2 != a2
                    )
                ):
                    update_buffer()
                    cluster1 = p1
                    cluster2 = p2
                    if alpha:
                        a_cluster1 = a1
                        a_cluster2 = a2
                    n = 0
                n += 1
            # Rest of the line
            update_buffer()
            if row_no < height:  # last line not yet rendered
                buf_write("\033[0m\n")

        if height % 2:
            cluster1 = last_rgb[0]
            a_cluster1 = last_alpha[0]
            n = 0
            for p1, a1 in zip(last_rgb, last_alpha):
                if p1 != cluster1 or (
                    alpha and a_cluster1 != a1 == 0 or 0 == a_cluster1 != a1
                ):
                    if alpha and a_cluster1 == 0:
                        buf_write("\033[0m")
                        buf_write(" " * n)
                    else:
                        buf_write(_FG_FMT % cluster1)
                        buf_write(_UPPER_PIXEL * n)
                    cluster1 = p1
                    if alpha:
                        a_cluster1 = a1
                    n = 0
                n += 1
            # Last cluster
            if alpha and a_cluster1 == 0:
                buf_write("\033[0m")
                buf_write(" " * n)
            else:
                buf_write(_FG_FMT % cluster1)
                buf_write(_UPPER_PIXEL * n)

        buf_write("\033[0m")  # Reset color after last line
        buffer.seek(0)  # Reset buffer pointer

        return buffer.getvalue()

    def _renderer(self, renderer: FunctionType, check_size: bool = False) -> Any:
        """Performs common render preparations and a rendering operation.

        Args:
            renderer: The function to perform the specifc rendering operation for the
              caller of this function (``_renderer()``).
              This function should accept just one argument, the PIL image.
            check_size: Determines whether or not the image's set size (if any) is
              checked to see if still fits into the terminal.

        Returns:
            The return value of *renderer*.

        Raises:
            ValueError: Render size or scale too small.

        NOTE:
            * If the ``set_size()`` method was previously used to set the *render size*,
              (directly or not), the last value of its *check_height* parameter
              is taken into consideration, for non-animated images.
        """
        if self._closed:
            raise TermImageException("This image has been finalized")

        try:
            reset_size = False
            if not self._size:  # Size is unset
                self.set_size()
                reset_size = True
            # If the set size is larger than terminal size but the set scale makes
            # it fit in, then it's all good.
            elif check_size:
                columns, lines = map(
                    sub,
                    get_terminal_size(),
                    (self.__h_allow, self.__v_allow),
                )

                if any(
                    map(
                        gt,
                        # the compared height will be 0 when `__check_height` is `False`
                        # and the terminal height should never be < 0
                        map(mul, self.rendered_size, (1, self.__check_height)),
                        (columns, lines),
                    )
                ):
                    raise InvalidSize(
                        "Seems the terminal has been resized or font ratio has been "
                        "changed since the image render size was set and the image "
                        "can no longer fit into the terminal"
                    )

                # Reaching here means it's either valid or `__check_height` is `False`
                # Hence, there's no need to check `__check_height`
                if self._is_animated and self.rendered_height > lines:
                    raise InvalidSize(
                        "The image height cannot be greater than the terminal height "
                        "for animated images"
                    )

            image = (
                Image.open(self._source)
                if isinstance(self._source, str)
                else self._source
            )

            return renderer(image)

        finally:
            self._buffer.seek(0)  # Reset buffer pointer
            self._buffer.truncate()  # Clear buffer
            if reset_size:
                self._size = None

    def _valid_size(
        self,
        width: Optional[int],
        height: Optional[int],
        h_allow: int = 0,
        v_allow: int = 2,
        *,
        maxsize: Optional[Tuple[int, int]] = None,
        check_height: bool = True,
        ignore_oversize: bool = False,
    ) -> Tuple[int, int]:
        """Generates a *render size* tuple and checks if the resulting *rendered size*
        is valid.

        Args:
            ignore_oversize: If ``True``, the validity of the resulting *rendered size*
              is not checked.

        See the description of ``set_size()`` for the other parameters.

        Returns:
            A valid *render size* tuple.
        """
        ori_width, ori_height = self._original_size

        columns, lines = maxsize or map(sub, get_terminal_size(), (h_allow, v_allow))
        for name in ("columns", "lines"):
            if locals()[name] <= 0:
                raise InvalidSize(f"Maximum amount of available {name} too small")

        # Two pixel rows per line
        rows = (lines) * 2

        # NOTE: The image scale is not considered since it should never be > 1

        if width is None is height:
            if not check_height:
                width = columns * _pixel_ratio
                return (round(width), round(ori_height * width / ori_width))

            # The smaller fraction will always fit into the larger fraction
            # Using the larger fraction with cause the image not to fit on the axis with
            # the smaller fraction
            factor = min(map(truediv, (columns, rows), (ori_width, ori_height)))
            width, height = map(round, map(mul, (factor,) * 2, (ori_width, ori_height)))

            # The width will later be divided by the pixel-ratio when rendering
            # Not be rounded at this point since the value used for further calculations
            # Rounding here could result in a new rendered width that's off by 1 or 2
            # when dealing with some odd (non-even) widths
            rendered_width = width / _pixel_ratio

            if round(rendered_width) <= columns:
                return (width, height)
            else:
                # Adjust the width such that the rendered width is exactly the maximum
                # number of columns and adjust the height proportionally
                return (
                    # w1 = rw1 * (w0 / rw0)
                    round(columns * width / rendered_width),
                    # h1 = h0 * (w1 / w0) == h0 * (rw1 / rw0)
                    round(height * columns / rendered_width),
                )
        elif width is None:
            width = round((height / ori_height) * ori_width)
        elif height is None:
            height = round((width / ori_width) * ori_height)

        if not ignore_oversize and (
            # The width will later be divided by the pixel-ratio when rendering
            round(width / _pixel_ratio) > columns
            or (check_height and height > rows)
        ):
            raise InvalidSize(
                "The resulting rendered size will not fit into the terminal"
            )

        return (width, height)


# Reserved
def _color(text: str, fg: tuple = (), bg: tuple = ()) -> str:
    """Prepends *text* with ANSI 24-bit color escape codes
    for the given foreground and/or background RGB values.

    The color code is ommited for any of *fg* or *bg* that is empty.
    """
    return (_FG_FMT * bool(fg) + _BG_FMT * bool(bg) + "%s") % (*fg, *bg, text)


# The pixel ratio is always used to adjust the width and not the height, so that the
# image can fill the terminal screen as much as possible.
# The final width is always rounded, but that should never be an issue
# since it's also rounded during size validation.
_pixel_ratio = 1.0  # Default
