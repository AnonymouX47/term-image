"""The main term-img module"""

from __future__ import annotations

__all__ = ("TermImage",)

import io
import os
import re
import requests
import time
from math import ceil
from operator import gt, mul, truediv
from random import randint
from shutil import get_terminal_size

from PIL import Image, UnidentifiedImageError
from typing import Optional, Tuple, Union
from urllib.parse import urlparse

from .exceptions import InvalidSize, URLNotFoundError


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
        - image: Image to be rendered.
        - width: The width to render the image with.
        - height: The height to render the image with.
        - scale: The image render scale on respective axes.

    NOTE:
        - _width_ is not neccesarily the exact number of columns that'll be used
          to render the image. That is influenced by the set font-ratio.
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
                "Expected a 'PIL.Image.Image' instance for 'image' "
                f"(got: {type(image).__name__!r})."
            )

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

        Format specification:

            `[[h_align][width]][.[v_align][height]][#[threshold|bgcolor]]`

            - h_align: '<' | '|' | '>' (default: '|')
            - width: Integer padding width (default: terminal width)
            - v_align: '^' | '-' | '_'  (default: '-')
            - height: Integer padding height
              (default: terminal height, with a 2-line allowance).
            - #: Transparency setting.
              - If absent, transparency is enabled.
              - threshold: Alpha ratio above which pixels are taken as opaque
                e.g '.0', '.325043', '.99999' (0.0 <= threshold < 1.0).
              - bgcolor: Hex color with which transparent background should be replaced
                e.g ffffff, 7faa52.
              - If neither _threshold_ nor _bgcolor_ is present, but '#' is present,
                a black background is used.

        Fields within `[]` are optional, `|` implies mutual exclusivity.
        _width_ and _height_ are in units of columns and lines, repectively.
        """
        match = _FORMAT_SPEC.fullmatch(spec)
        if not match:
            raise ValueError("Invalid format specifier")

        _, h_align, width, _, v_align, height, alpha, threshold_or_bg = match.groups()

        width = width and int(width)
        height = height and int(height)

        reset_size = False
        if not self._size:  # Size is unset
            self._size = self._valid_size(None, None)
            reset_size = True

        try:
            # Only the first/set frame for animated images
            return self._format_image(
                self.__draw_image(
                    (
                        Image.open(self._source)
                        if isinstance(self._source, str)
                        else self._source
                    ),
                    (
                        threshold_or_bg
                        and (
                            "#" + threshold_or_bg
                            if _HEX_COLOR_FORMAT.fullmatch("#" + threshold_or_bg)
                            else float(threshold_or_bg)
                        )
                        if alpha
                        else 40 / 255
                    ),
                ),
                *self.__check_formating(h_align, width, v_align, height),
            )
        finally:
            self._buffer.seek(0)  # Reset buffer pointer
            self._buffer.truncate()  # Clear buffer
            if reset_size:
                self._size = None

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
        reset_size = False
        if not self._size:  # Size is unset
            self._size = self._valid_size(None, None)
            reset_size = True

        try:
            # Only the first/set frame for animated images
            return self.__draw_image(
                (
                    Image.open(self._source)
                    if isinstance(self._source, str)
                    else self._source
                ),
                40 / 255,
            )
        finally:
            self._buffer.seek(0)  # Reset buffer pointer
            self._buffer.truncate()  # Clear buffer
            if reset_size:
                self._size = None

    # Properties

    columns = property(
        lambda self: round(
            (self._size or self._valid_size(None, None))[0]
            * self._scale[0]
            / _pixel_ratio
        ),
        doc="The number of columns that the rendered image will occupy on the terminal",
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
        doc="""
        Image render height (`None` when render size is unset)

        Settable values:
            - `None`: Sets the render size to the automatically calculated one.
            - A positive integer: Sets the render height to the given value and
              the width proprtionally.

        The image is actually rendered using half this number of lines
        """,
    )

    @height.setter
    def height(self, height: int) -> None:
        self._size = self._valid_size(None, height)

    is_animated = property(
        lambda self: self._is_animated,
        doc="True if the image is animated. Otherwise, False.",
    )

    lines = property(
        lambda self: ceil(
            (self._size or self._valid_size(None, None))[1] * self._scale[1] / 2
        ),
        doc="The number of lines that the rendered image will occupy on the terminal",
    )

    original_size = property(
        lambda self: self._original_size, doc="Original image size"
    )

    n_frames = property(
        lambda self: self._n_frames if self._is_animated else 1,
        doc="Number of frames in an image",
    )

    @property
    def rendered_size(self) -> Tuple[int, int]:
        """The number of columns and lines (respectively) that the rendered image will
        occupy on the terminal.
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
                raise ValueError(f"Scale value out of range (got: {scale})")
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
        lambda self: self._scale[1],
        doc="""
        Image y-ayis render scale

        A scale value must be a float such that 0.0 < y <= 1.0.
        """,
    )

    @scale_y.setter
    def scale_y(self, y: float) -> None:
        self._scale[1] = self.__check_scale_2(y)

    size = property(
        lambda self: self._size,
        doc="""Image render size (`None` when render size is unset)

        Setting this to `None` unsets the render size, so that it's automatically
        calculated whenever the image is rendered.
        """,
    )

    @size.setter
    def size(self, value: None) -> None:
        if value is not None:
            raise TypeError("The only acceptable value is `None`")
        self._size = value

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
        lambda self: self._size and self._size[0],
        doc="""
        Image render width (`None` when render size is unset)

        Settable values:
            - `None`: Sets the render size to the automatically calculated one.
            - A positive integer: Sets the render width to the given value and
              the height proprtionally.
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
        alpha: Optional[float] = 40 / 255,
    ) -> None:
        """Print an image to the terminal, with optional alignment and padding.

        Args:
            - h_align: Horizontal alignment ("left", "center" or "right").
            - pad_width: No of columns within which to align the image.
              Excess columns are filled with spaces. (default: terminal width)
            - v_align: Vertical alignment ("top", "middle" or "bottom").
            - pad_height: No of lines within which to align the image.
              Excess lines are filled with spaces.
              (default: terminal height, with a 2-line allowance).
            - alpha: Transparency setting.
              - If `None`, transparency is disabled (i.e black background).
              - If a float, 0.0 <= x < 1.0, specifies the alpha ratio above which pixels
                are taken as opaque.
              - If a string, specifies a hex color with which transparent background
                should be replaced.

        Raises:
            - .exceptions.InvalidSize: if the terminal has been resized in such a way
            that it can no longer fit the previously set image render size.
            - TypeError: if any argument is of an inappropriate type.
            - ValueError: if any argument has an unexpected/invalid value.
        """
        h_align, pad_width, v_align, pad_height = self.__check_formating(
            h_align, pad_width, v_align, pad_height
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

        if not self._size:  # Size is unset
            self._size = self._valid_size(None, None)
            reset_size = True
        else:
            # If the set size is larger than terminal size but the set scale makes
            # it fit in, then it's all good.
            if any(map(gt, self.rendered_size, get_terminal_size())):
                raise InvalidSize(
                    "Seems the terminal has been resized or font-ratio has been "
                    "changed since the image render size was set and the image can "
                    "no longer fit into the terminal"
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
                self.__display_animated(
                    image, alpha, h_align, pad_width, v_align, pad_height
                )
            else:
                print(
                    self._format_image(
                        self.__draw_image(image, alpha),
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
                f"File path must be a string (got: {type(filepath).__name__!r})."
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

        new = cls(Image.open(filepath), **size_scale)
        new._source = filepath
        new.__url = url
        return new

    def seek(self, pos: int) -> None:
        """Change current image frame (Frame numbers start from 0 (zero))"""
        if not isinstance(pos, int):
            raise TypeError(f"Invalid seek position type (got: {type(pos).__name__})")
        if not 0 <= pos < self._n_frames if self._is_animated else pos:
            raise ValueError(
                f"Invalid frame number (got: {pos}, n_frames={self._n_frames})"
            )
        if self._is_animated:
            self._seek_position = pos

    def tell(self) -> int:
        """Return the current image frame number"""
        return self._seek_position if self._is_animated else 0

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
                raise ValueError(f"Padding width must be positive (got: {width})")
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
            raise ValueError(f"Padding height must be positive (got: {height})")

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
                f"'scale' must be a tuple of two floats, 0.0 < x <= 1.0 (got: {scale})"
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
            raise ValueError(f"Scale value out of range (got: {value})")
        return value

    def __display_animated(
        self, image: Image.Image, alpha: Optional[float], *fmt: Union[None, str, int]
    ) -> None:
        """Print an animated GIF image on the terminal

        This is done infinitely but can be canceled with `Ctrl-C`.
        """
        height = max(
            (fmt or (None,))[-1] or get_terminal_size()[1] - 2,
            self.lines,
        )
        try:
            while True:
                for frame in range(0, image.n_frames):
                    image.seek(frame)
                    print(self._format_image(self.__draw_image(image, alpha), *fmt))
                    self._buffer.truncate()  # Clear buffer
                    time.sleep(0.1)
                    # Move cursor up to the first line of the image
                    print("\033[%dA" % height, end="")
        finally:
            # Move the cursor to the line after the image
            # Prevents "overlayed" output on the terminal
            print("\033[%dB" % height, end="", flush=True)

    def __draw_image(self, image: Image.Image, alpha: Optional[float]) -> str:
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

        width, height = map(
            round, map(mul, self._size, map(truediv, self._scale, (_pixel_ratio, 1)))
        )
        image = image.convert("RGBA").resize((width, height))
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
        cols, rows = self.rendered_size

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
                    f"(got: {argname} of type {type(x).__name__!r})"
                )
            if None is not x <= 0:
                raise ValueError(f"{argname} must be positive (got: {x})")

        ori_width, ori_height = self._original_size

        columns, lines = maxsize or get_terminal_size()
        if not maxsize:
            lines -= 2  # A 2-line allowance for the shell prompt
        # Two pixel rows per line
        rows = (lines) * 2

        # NOTE: The image scale is not considered since it should never be > 1

        if width is None is height:
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
            or height > rows
        ):
            raise InvalidSize(
                "The resulting render size will not fit into the terminal"
            )

        return (width, height)


# Reserved
def _color(text: str, fg: tuple = (), bg: tuple = ()) -> str:
    """Prepend _text_ with ANSI 24-bit color codes
    for the given foreground and/or backgroung RGB values.

    The color code is ommited for any of 'fg' or 'bg' that is empty.
    """
    return (_FG_FMT * bool(fg) + _BG_FMT * bool(bg) + "%s") % (*fg, *bg, text)


# The pixel ratio is always used to adjust the width and not the height, so that the
# image can fill the terminal screen as much as possible.
# The final width is always rounded, but that should never be an issue
# since it's also rounded during size validation.
_pixel_ratio = None  # Set by `.set_font_ratio()`
