"""The main term-img module"""

from __future__ import annotations

__all__ = ("TermImage",)

import io
import os
import requests
import time
from math import ceil
from operator import truediv
from random import randint
from shutil import get_terminal_size

from PIL import Image, GifImagePlugin, UnidentifiedImageError
from typing import Optional, Tuple
from urllib.parse import urlparse

from .exceptions import InvalidSize, URLNotFoundError


FG_FMT: str = "\033[38;2;%d;%d;%dm"
BG_FMT: str = "\033[48;2;%d;%d;%dm"
PIXEL: str = "\u2580"  # upper-half block element


class TermImage:
    """Text-printable image

    Args:
        - image: Image to be rendered.
        - width: The width to render the image with.
        - height: The height to render the image with.

    NOTE:
        - _width_ is the exact number of columns that'll be used on the terminal.
        - _height_ is **2 times** the number of lines that'll be used on the terminal.
        - If neither is given or `None`, the size is automatically determined
          when the image is to be rendered, such that it can fit within the terminal.
    """

    # Special Methods

    def __init__(
        self,
        image: Image.Image,
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> None:
        """See class description"""
        if not isinstance(image, Image.Image):
            raise TypeError(
                "Expected a 'PIL.Image.Image' instance for 'image',"
                f" got {type(image).__name__!r}."
            )

        self.__source = image
        self.__buffer = io.StringIO()
        self.__size = (
            None if width is None is height else self._valid_size(width, height)
        )

    def __del__(self) -> None:
        self.__buffer.close()
        if (
            hasattr(self, f"_{__class__.__name__}__url")
            and os.path.exists(self.__source)
            # The file might not exist for whatever reason.
        ):
            os.remove(self.__source)

    def __repr__(self) -> str:
        return "<{}(source={!r}, size={})>".format(
            type(self).__name__,
            (
                self.__url
                if hasattr(self, f"_{__class__.__name__}__url")
                else self.__source
            ),
            self.__size,
        )

    def __str__(self) -> str:
        # Only the first frame for GIFs
        reset_size = False
        if not self.__size:  # Size is unset
            self.__size = self._valid_size(None, None)
            reset_size = True

        try:
            txt = self.__draw_image(
                Image.open(self.__source)
                if isinstance(self.__source, str)
                else self.__source
            )
        finally:
            self.__buffer.seek(0)  # Reset buffer pointer
            self.__buffer.truncate()  # Clear buffer
            if reset_size:
                self.__size = None

        return txt

    # Properties

    width = property(
        lambda self: self.__size[0],
        doc="""
        Width of the rendered image

        Setting this affects the height proportionally to keep the image in scale
        """,
    )
    height = property(
        lambda self: self.__size[1],
        doc="""
        Height of the rendered image

        Setting this affects the width proportionally to keep the image in scale

        The image is actually rendered using half this number of lines
        (keeps the image in proper scale on most terminals)
        """,
    )
    size = property(lambda self: self.__size, doc="Image render size")

    @width.setter
    def width(self, width: int) -> None:
        self.__size = self._valid_size(width, None)

    @height.setter
    def height(self, height: int) -> None:
        self.__size = self._valid_size(None, height)

    # Public Methods

    def draw_image(self) -> None:
        """Print an image to the terminal

        Raises:
            - .exceptions.InvalidSize: if the terminal has been resized in such a way
            that it can no longer fit the previously set image render size.
        """
        if not self.__size:  # Size is unset
            self.__size = self._valid_size(None, None)
            reset_size = True
        else:
            width, height = self.__size
            columns, lines = get_terminal_size()
            # A 3-line allowance for the extra blank line and maybe the shell prompt
            if width > columns or height > (lines - 3) * 2:
                raise InvalidSize(
                    "Seems the terminal has been resized since the render size was set"
                )
            reset_size = False

        image = (
            Image.open(self.__source)
            if isinstance(self.__source, str)
            else self.__source
        )

        try:
            if isinstance(image, GifImagePlugin.GifImageFile):
                self.__display_gif(image)
            else:
                print(self.__draw_image(image))
        finally:
            self.__buffer.seek(0)  # Reset buffer pointer
            self.__buffer.truncate()  # Clear buffer
            print("\033[0m")  # Reset color
            if reset_size:
                self.__size = None

    @classmethod
    def from_file(
        cls,
        filepath: str,
        **size,
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

        new = cls(Image.open(filepath), **size)
        new.__source = filepath
        return new

    @classmethod
    def from_url(
        cls,
        url: str,
        **size,
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

        basedir = os.path.join(os.path.expanduser("~"), ".term_img")
        if not os.path.isdir(basedir):
            os.mkdir(basedir)

        filepath = os.path.join(basedir, os.path.basename(urlparse(url).path))
        while os.path.exists(filepath):
            filepath += str(randint(0, 9))
        with open(filepath, "wb") as image_writer:
            image_writer.write(response.content)

        new = cls(Image.open(filepath), **size)
        new.__source = filepath
        new.__url = url
        return new

    # Private Methods

    @staticmethod
    def __color(text: str, fg: tuple = (), bg: tuple = ()) -> str:
        """Prepend _text_ with ANSI 24-bit color codes
        for the given foreground and/or backgroung RGB values.

        The color code is ommited for any of 'fg' or 'bg' that is empty.
        """
        return (FG_FMT * bool(fg) + BG_FMT * bool(bg) + "%s") % (*fg, *bg, text)

    def __display_gif(self, image: GifImagePlugin.GifImageFile) -> None:
        """Print an animated GIF image on the terminal

        This is done infinitely but can be canceled with `Ctrl-C`.
        """
        height = ceil(self.__size[1] / 2)
        try:
            while True:
                for frame in range(0, image.n_frames):
                    image.seek(frame)
                    print(self.__draw_image(image))
                    self.__buffer.truncate()  # Clear buffer
                    time.sleep(0.1)
                    # Move cursor up to the first line of the image
                    print("\033[%dA" % height, end="")
        finally:
            # Move the cursor to the line after the image
            # Prevents "overlayed" output on the terminal
            print("\033[%dB" % height)

    def __draw_image(self, image: Image.Image) -> str:
        """Convert entire image pixel data to a color-coded string

        Two pixels per character using FG and BG colors.
        """
        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        # Eliminate attribute resolution cost
        buffer = self.__buffer
        buf_write = buffer.write

        def update_buffer():
            buf_write(FG_FMT % cluster_fg)
            buf_write(BG_FMT % cluster_bg)
            buf_write(PIXEL * n)

        image = image.resize(self.__size)
        pixels = tuple(image.convert("RGB").getdata())
        width, height = self.__size
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

        ori_width, ori_height = (
            Image.open(self.__source)
            if isinstance(self.__source, str)
            else self.__source
        ).size

        columns, lines = maxsize or get_terminal_size()
        # A 3-line allowance for the extra blank line and maybe the shell prompt
        # Two pixel rows per line
        if not maxsize:
            lines -= 3
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
