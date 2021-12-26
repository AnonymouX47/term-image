"""The main term-img module"""

from __future__ import annotations

__all__ = ("TermImage",)

import io
import os
import re
import requests
import time
from math import ceil
from operator import mul, truediv
from random import randint
from shutil import get_terminal_size

from PIL import Image, UnidentifiedImageError
from typing import Optional, Tuple, Union
from urllib.parse import urlparse

from .exceptions import InvalidSize, URLNotFoundError


FG_FMT: str = "\033[38;2;%d;%d;%dm"
BG_FMT: str = "\033[48;2;%d;%d;%dm"
PIXEL: str = "\u2580"  # upper-half block element
FORMAT_SPEC = re.compile(r"(([<|>])?(\d*))?(\.(([-^_])?(\d*)))?", re.ASCII)


class TermImage:
    """Text-printable image

    Args:
        - image: Image to be rendered.
        - width: The width to render the image with.
        - height: The height to render the image with.
        - scale: The image render scale on respective axes.

    NOTE:
        - _width_ is the exact number of columns that'll be used on the terminal.
        - _height_ is **2 times** the number of lines that'll be used on the terminal.
        - If neither is given or `None`, the size is automatically determined
          when the image is to be rendered, such that it can fit within the terminal.
        - The size is multiplied by the scale on each axis respectively before the image
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
    ) -> None:
        """See class description"""
        if not isinstance(image, Image.Image):
            raise TypeError(
                "Expected a 'PIL.Image.Image' instance for 'image',"
                f" got {type(image).__name__!r}."
            )

        self._is_animated = hasattr(image, "is_animated") and image.is_animated
        self._source = image
        self._buffer = io.StringIO()
        self._original_size = image.size
        self._size = (
            None if width is None is height else self._valid_size(width, height)
        )
        self._scale = []
        self._scale[:] = self.__check_scale(scale)

    def __del__(self) -> None:
        try:
            self._buffer.close()
        except AttributeError:
            # When an exception is raised during instance creation or initialization.
            pass

        if (
            hasattr(self, f"_{__class__.__name__}__url")
            and os.path.exists(self._source)
            # The file might not exist for whatever reason.
        ):
            os.remove(self._source)

    def __format__(self, spec) -> str:
        """Image alignment and padding

        Format specification: "[[h_align][width]][.[v_align][height]]"
            - h_align: '<' | '|' | '>' (default: '|')
            - width: Integer  (default: terminal width)
            - v_align: '^' | '-' | '_'  (default: '-')
            - height: Integer  (default: terminal height, with a 2-line allowance)

        All fields are optional with defaults in parentheses.
        """
        match = FORMAT_SPEC.fullmatch(spec)
        if not match:
            raise ValueError("Invalid format specifier")

        _, h_align, width, _, _, v_align, height = match.groups()
        h_align = h_align or None
        v_align = v_align or None
        width = None if width in {None, ""} else int(width)
        height = None if height in {None, ""} else int(height)

        return self._format_image(
            self.__str__(),
            *self.__check_formating(h_align, width, v_align, height),
        )

    def __repr__(self) -> str:
        return "<{}(source={!r}, size={})>".format(
            type(self).__name__,
            (
                self.__url
                if hasattr(self, f"_{__class__.__name__}__url")
                else self._source
            ),
            self._size,
        )

    def __str__(self) -> str:
        # Only the first/set frame for animated images
        reset_size = False
        if not self._size:  # Size is unset
            self._size = self._valid_size(None, None)
            reset_size = True

        try:
            return self.__draw_image(
                Image.open(self._source)
                if isinstance(self._source, str)
                else self._source
            )
        finally:
            self._buffer.seek(0)  # Reset buffer pointer
            self._buffer.truncate()  # Clear buffer
            if reset_size:
                self._size = None

    # Properties

    is_animated = property(
        lambda self: self._is_animated,
        doc="True if the image is animated. Otherwise, False.",
    )

    height = property(
        lambda self: self._size[1],
        doc="""
        Height of the rendered image

        Setting this affects the width proportionally to keep the image in scale

        The image is actually rendered using half this number of lines
        (keeps the image in proper scale on most terminals)
        """,
    )

    @height.setter
    def height(self, height: int) -> None:
        self._size = self._valid_size(None, height)

    original_size = property(
        lambda self: self._original_size, doc="Original image size"
    )

    scale = property(
        lambda self: tuple(self._scale),
        doc="""
        Image render scale

        Allowed values are:
            - A float; sets both axes.
            - A tuple of two floats; sets for (x, y) respectively.

        A scale value must be such that 0.0 < value <= 1.0.
        """,
    )

    @scale.setter
    def scale(self, scale: Union[float, Tuple[float, float]]) -> None:
        if isinstance(scale, float):
            if not 0.0 < scale <= 1.0:
                raise ValueError(f"Scale value out of range; got: {scale}")
            self._scale[:] = (scale,) * 2
        elif isinstance(scale, tuple):
            self._scale[:] = self.__check_scale(scale)
        else:
            raise TypeError("Given value must be a float or a tuple of floats")

    scale_x = property(
        lambda self: self._scale[0],
        doc="""
        Image x-axis render scale

        A scale value must be a float such that 0.0 < x <= 1.0.
        """,
    )

    @scale_x.setter
    def scale_x(self, x: float) -> None:
        self._scale[0] = self.__check_scale_2(x)

    scale_y = property(
        lambda self: self._scale[0],
        doc="""
        Image y-ayis render scale

        A scale value must be a float such that 0.0 < y <= 1.0.
        """,
    )

    @scale_y.setter
    def scale_y(self, y: float) -> None:
        self._scale[1] = self.__check_scale_2(y)

    size = property(lambda self: self._size, doc="Image render size")

    source = property(
        lambda self: (
            self.__url if hasattr(self, f"_{__class__.__name__}__url") else self._source
        ),
        doc="""
        Source from which the instance was initialized

        Can be a PIL image, file path or URL.
        """,
    )

    width = property(
        lambda self: self._size[0],
        doc="""
        Width of the rendered image

        Setting this affects the height proportionally to keep the image in scale
        """,
    )

    @width.setter
    def width(self, width: int) -> None:
        self._size = self._valid_size(width, None)

    # Public Methods

    def draw_image(
        self,
        h_align: Optional[str] = "center",
        pad_width: Optional[int] = None,
        v_align: Optional[str] = "middle",
        pad_height: Optional[int] = None,
    ) -> None:
        """Print an image to the terminal (with optional alignment and padding)

        Args:
            - h_align: Horizontal alignment ("left", "center" or "right").
            - pad_width: Padding width (default: terminal width).
            - v_align: Vertical alignment ("top", "middle" or "bottom").
            - pad_height: Padding height (default: terminal height,
              with a 2-line allowance).

        Raises:
            - .exceptions.InvalidSize: if the terminal has been resized in such a way
            that it can no longer fit the previously set image render size.
            - TypeError: if padding width/height value is of innapropriate type.
            - ValueError: if any argument has an unexpected/invalid value.
        """
        h_align, pad_width, v_align, pad_height = self.__check_formating(
            h_align, pad_width, v_align, pad_height
        )

        if not self._size:  # Size is unset
            self._size = self._valid_size(None, None)
            reset_size = True
        else:
            width, height = map(ceil, map(mul, self._size, self._scale))
            columns, lines = get_terminal_size()
            # A 2-line allowance for the shell prompt
            if width > columns or height > (lines - 2) * 2:
                raise InvalidSize(
                    "Seems the terminal has been resized since the render size was set"
                )
            reset_size = False

        image = (
            Image.open(self._source) if isinstance(self._source, str) else self._source
        )

        try:
            if self._is_animated:
                if None is not pad_height > get_terminal_size()[1] - 2:
                    raise ValueError(
                        "Padding height must not be larger than the terminal height, "
                        "for animated images"
                    )
                self.__display_animated(image, h_align, pad_width, v_align, pad_height)
            else:
                print(
                    self._format_image(
                        self.__draw_image(image),
                        h_align,
                        pad_width,
                        v_align,
                        pad_height,
                    ),
                    end="",
                    flush=True,
                )
        finally:
            self._buffer.seek(0)  # Reset buffer pointer
            self._buffer.truncate()  # Clear buffer
            print("\033[0m")  # Always reset color
            if reset_size:
                self._size = None

    @classmethod
    def from_file(
        cls,
        filepath: str,
        **size_scale,
    ) -> TermImage:
        """Create a `TermImage` object from an image file

        Args:
            - filepath: Relative/Absolute path to an image file.
            - See the class description for others.

        Raises:
            - TypeError: if _filepath_ is not a string.
            - FileNotFoundError: if the given path does not exist.
            - Propagates `UnidentifiedImageError` and `IsADirectoryError`
            from PIL.Image.open()
        """
        if not isinstance(filepath, str):
            raise TypeError(
                f"File path must be a string, got {type(filepath).__name__!r}."
            )

        # Intentionally propagates `UnidentifiedImageError` and `IsADirectoryError`
        # since the messages are OK.
        try:
            Image.open(filepath)
        except FileNotFoundError:
            raise FileNotFoundError(f"No such file: {filepath!r}") from None

        new = cls(Image.open(filepath), **size_scale)
        new._source = os.path.realpath(filepath)
        return new

    @classmethod
    def from_url(
        cls,
        url: str,
        **size_scale,
    ) -> TermImage:
        """Create a `TermImage` object from an image url

        Args:
            - url: URL of an image file.
            - See the class description for others.

        Raises:
            - TypeError: if _url_ is not a string.
            - ValueError: if the given URL is invalid.
            - .exceptions.URLNotFoundError: if the URL does not exist.
            - Propagates connection-related errors from `requests.get()`.
            - Propagates `UnidentifiedImageError` from `PIL.Image.open()`.
        """
        if not isinstance(url, str):
            raise TypeError(f"URL must be a string, got {type(url).__name__!r}.")
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

        new = cls(Image.open(filepath), **size_scale)
        new._source = filepath
        new.__url = url
        return new

    # Private Methods

    @staticmethod
    def __check_formating(
        h_align: Optional[str] = None,
        width: Optional[int] = None,
        v_align: Optional[str] = None,
        height: Optional[int] = None,
    ) -> Tuple[Union[str, int, None]]:
        """Validate and translate literal formatting arguments

        Returns: The respective arguments appropriate for `_format_image()`.
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
                raise ValueError(f"Padding width must be positive, got: {width}")
            if width > get_terminal_size()[0]:
                raise ValueError("Padding width larger than terminal width")

        if v_align is not None:
            align = {"top": "^", "middle": "-", "bottom": "_"}.get(v_align, v_align)
            if not align:
                raise ValueError(f"Invalid vertical alignment option: {v_align!r}")
            v_align = align

        if not isinstance(height, (type(None), int)):
            raise TypeError("Wrong type; Padding height must be None or an integer.")
        if None is not height <= 0:
            raise ValueError(f"Padding height must be positive, got: {height}")

        return h_align, width, v_align, height

    @staticmethod
    def __check_scale(scale: Tuple[float, float]) -> Tuple[float, float]:
        """Check a scale tuple

        Returns: The scale tuple, if valid.

        Raises:
            - TypeError, if the object is not a tuple of floats.
            - ValueError, if the object is not a tuple of two floats, 0.0 < x <= 1.0.
        """
        if not (isinstance(scale, tuple) and all(isinstance(x, float) for x in scale)):
            raise TypeError("'scale' must be a tuple of floats")

        if not (len(scale) == 2 and all(0.0 < x <= 1.0 for x in scale)):
            raise ValueError(
                f"'scale' must be a tuple of two floats, 0.0 < x <= 1.0; got: {scale}"
            )
        return scale

    @staticmethod
    def __check_scale_2(value: float) -> float:
        """Check a single scale value

        Returns: The scale value, if valid.

        Raises:
            - TypeError, if the object is not a float.
            - ValueError, if the value is not within range 0.0 < x <= 1.0.
        """
        if not isinstance(value, float):
            raise TypeError("Given value must be a float")
        if not 0.0 < value <= 1.0:
            raise ValueError(f"Scale value out of range; got: {value}")
        return value

    @staticmethod
    def __color(text: str, fg: tuple = (), bg: tuple = ()) -> str:
        """Prepend _text_ with ANSI 24-bit color codes
        for the given foreground and/or backgroung RGB values.

        The color code is ommited for any of 'fg' or 'bg' that is empty.
        """
        return (FG_FMT * bool(fg) + BG_FMT * bool(bg) + "%s") % (*fg, *bg, text)

    def __display_animated(self, image: Image.Image, *fmt) -> None:
        """Print an animated GIF image on the terminal

        This is done infinitely but can be canceled with `Ctrl-C`.
        """
        height = ceil(self._size[1] * self._scale[1] / 2)
        try:
            while True:
                for frame in range(0, image.n_frames):
                    image.seek(frame)
                    print(self._format_image(self.__draw_image(image), *fmt))
                    self._buffer.truncate()  # Clear buffer
                    time.sleep(0.1)
                    # Move cursor up to the first line of the image
                    print("\033[%dA" % height, end="")
        finally:
            # Move the cursor to the line after the image
            # Prevents "overlayed" output on the terminal
            print("\033[%dB" % height, end="", flush=True)

    def __draw_image(self, image: Image.Image) -> str:
        """Convert entire image pixel data to a color-coded string

        Two pixels per character using FG and BG colors.
        """
        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        # Eliminate attribute resolution cost
        buffer = self._buffer
        buf_write = buffer.write

        def update_buffer():
            buf_write(BG_FMT % cluster_bg)
            if cluster_fg == cluster_bg:
                buf_write(" " * n)
            else:
                buf_write(FG_FMT % cluster_fg)
                buf_write(PIXEL * n)

        width, height = map(ceil, map(mul, self._size, self._scale))
        image = image.resize((width, height))
        pixels = tuple(image.convert("RGB").getdata())
        if height % 2:
            # Starting index of the last row (when height is odd)
            mark = width * (height // 2) * 2
            pixels, last_row = pixels[:mark], pixels[mark:]

        row_pairs = (
            (
                zip(pixels[x : x + width], pixels[x + width : x + width * 2]),
                (pixels[x], pixels[x + width]),
            )
            for x in range(0, len(pixels), width * 2)
        )

        row_no = 0
        # Two rows of pixels per line
        for row_pair, (cluster_fg, cluster_bg) in row_pairs:
            row_no += 2
            n = 0
            for fg, bg in row_pair:  # upper pixel -> FG, lower pixel -> BG
                # Color-code characters and write to buffer
                # when upper and/or lower pixel color changes
                if fg != cluster_fg or bg != cluster_bg:
                    update_buffer()
                    cluster_fg = fg
                    cluster_bg = bg
                    n = 0
                n += 1
            # Rest of the line
            update_buffer()
            if row_no < height:  # Excludes the last line
                buf_write("\033[0m\n")

        if height % 2:
            cluster_fg = last_row[0]
            n = 0
            for fg in last_row:
                if fg != cluster_fg:
                    buf_write(FG_FMT % cluster_fg)
                    buf_write(PIXEL * n)
                    cluster_fg = fg
                    n = 0
                n += 1
            # Last cluster
            buf_write(FG_FMT % cluster_fg)
            buf_write(PIXEL * n)

        buf_write("\033[0m")  # Reset color after last line
        buffer.seek(0)  # Reset buffer pointer

        return buffer.getvalue()

    def _format_image(
        self,
        render: str,
        h_align: Optional[str] = None,
        width: Optional[int] = None,
        v_align: Optional[str] = None,
        height: Optional[int] = None,
    ) -> str:
        """Format rendered image text

        All arguments should be passed through `__check_formatting()` first.
        """
        lines = render.splitlines()
        cols, rows = self._size or self._valid_size(None, None)
        rows = ceil(rows / 2)

        width = width or get_terminal_size()[0]
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

        height = height or get_terminal_size()[1] - 2
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

    def _valid_size(
        self,
        width: Optional[int],
        height: Optional[int],
        *,
        maxsize: Optional[Tuple[int, int]] = None,
        ignore_oversize: bool = False,
    ) -> Tuple[int, int]:
        """Generate size tuple from given height or width and
        check if the resulting render size is valid

        Returns: Valid size tuple.

        Raises:
            - ValueError: if
                - both width and height are specified, or
                - the specified dimension is non-positive.
            - .exceptions.InvalidSize: if the resulting size will not fit properly
            into the terminal or _maxsize_.

        If _ignore_oversize_ is True, the validity of the resulting render size
        is not checked.
        """
        if width is not None is not height:
            raise ValueError("Cannot specify both width and height")
        for argname, x in zip(("width", "height"), (width, height)):
            if not (x is None or isinstance(x, int)):
                raise TypeError(
                    f"{argname} must be an integer "
                    f"(got {argname} of type {type(x).__name__!r})"
                )
            if None is not x <= 0:
                raise ValueError(f"{argname} must be positive (got: {x})")

        ori_width, ori_height = self._original_size

        columns, lines = maxsize or get_terminal_size()
        if not maxsize:
            lines -= 2  # A 2-line allowance for the shell prompt
        # Two pixel rows per line
        rows = (lines) * 2

        if width is None is height:
            return tuple(
                round(x * min(map(truediv, (columns, rows), (ori_width, ori_height))))
                for x in (ori_width, ori_height)
            )
        elif width is None:
            width = round((height / ori_height) * ori_width)
        elif height is None:
            height = round((width / ori_width) * ori_height)

        if not ignore_oversize and (width > columns or height > rows):
            raise InvalidSize(
                "The resulting render size will not fit into the terminal"
            )

        return (width, height)
