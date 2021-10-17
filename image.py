"""The main img module"""

from __future__ import annotations

import io
import os
import requests
import time
from itertools import islice, zip_longest

from PIL import Image, GifImagePlugin
from typing import Optional, Tuple
from urllib.parse import urlparse


class DrawImage:
    """Text-printable image

    Args:
        _image_ -> Image to be drawn.
        _size_ -> The width and height to print the image with.

    The _size_ determines the exact number of lines and character cells
    that'll be used to print the image to the terminal.
    """
    PIXEL: str = "\u2580"  # upper-half block

    def __init__(
        self, image: Image.Image, size: Optional[Tuple[int, int]] = (24, 24)
    ) -> None:
        """See class description"""
        if not isinstance(image, Image.Image):
            raise TypeError(
                "Expected a 'PIL.Image.Image' instance for 'image',"
                f" got {type(image).__name__!r}."
            )
        self.__validate_size(size)

        self.__source = image.convert("RGB")
        self.__buffer = io.StringIO()
        self.size = size

    def __display_gif(self, image: GifImagePlugin.GifImageFile) -> None:
        """Print an animated GIF image on the terminal

        This is done infinitely but can be canceled with `Ctrl-C`.
        """
        try:
            while True:
                for frame in range(0, image.n_frames):
                    image.seek(frame)
                    print(self.__draw_image(image))
                    self.__buffer.truncate()  # Clear buffer
                    time.sleep(0.1)
                    # Move cursor up to the first line of the image
                    print(f"\033[{image.size[1]}A", end="")
        finally:
            # Move the cursor to the line after the image
            # Prevents "overlayed" output on the terminal
            print(f"\033[{self.size[1]}B")

    def draw_image(self) -> None:
        """Print an image to the terminal"""
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

    def __draw_image(self, image: Image.Image) -> str:
        """Convert entire image pixel data to a color-coded string

        Two pixels per character using FG and BG colors.
        """
        if self.size:
            image = image.resize(self.size)
        pixels = image.convert("RGB").getdata()
        len_pixels = len(pixels)
        width, height = image.size

        row_pairs = (
            (
                zip_longest(  # Includes last row when height is odd
                    islice(pixels, x, x + width),
                    islice(pixels, x + width, x + width * 2),
                    # The empty tuple is used to ensure the BG (lower pixel) color
                    # is not set on the last line when height is odd
                    fillvalue=(),
                ),
                # the final (x + width) will be out-of-range when height is odd
                (pixels[x], pixels[x + width] if x + width < len_pixels else ()),
            )
            for x in range(0, len_pixels, width * 2)
        )

        # Eliminate attribute resolution cost
        PIXEL = self.PIXEL
        buffer = self.__buffer
        color = self.__color

        row_no = 0
        # Two rows of pixels per line
        for row_pair, (cluster_fg, cluster_bg) in row_pairs:
            row_no += 2
            n = 0
            for fg, bg in row_pair:  # upper pixel -> FG, lower pixel -> BG
                # Color-code characters and write to buffer
                # when upper and/or lower pixel color changes
                if fg != cluster_fg or bg != cluster_bg:
                    buffer.write(color(PIXEL * n, cluster_fg, cluster_bg))
                    cluster_fg = fg
                    cluster_bg = bg
                    n = 0
                n += 1

            # Rest of the line
            buffer.write(color(PIXEL * n, cluster_fg, cluster_bg))

            # It's more efficient to write separate strings to the buffer separately
            # than concatenate and write together.
            if row_no < height:
                buffer.write("\033[0m\n")

        buffer.write("\033[0m")  # Reset color after last line
        buffer.seek(0)  # Reset buffer pointer

        return buffer.getvalue()

    @staticmethod
    def __color(text: str, fg: tuple = (), bg: tuple = ()) -> str:
        """Prepend _text_ with ANSI 24-bit color codes
        for the given foreground and/or backgroung RGB values.

        The color code is ommited for any of 'fg' or 'bg' that is empty.
        """
        return (
            "\033[38;2;%d;%d;%dm" * bool(fg)
            + "\033[48;2;%d;%d;%dm" * bool(bg)
            + "%s"
        ) % (*fg, *bg, text)

    @classmethod
    def from_file(
        cls, filepath: str, size: Optional[Tuple[int, int]] = None
    ) -> DrawImage:
        """Create a `DrawImage` object from an image file

        Args:
            _filepath_ -> Relative/Absolute path to an image file.
            _size_ -> See class description.
        """
        if not isinstance(filepath, str):
            raise TypeError(
                f"File path must be a string, got {type(filepath).__name__!r}."
            )
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"{filepath!r} not found")

        new = cls(Image.new("P", (0, 0)), size)
        new.__source = filepath
        return new

    @classmethod
    def from_url(cls, url: str, size: Optional[Tuple[int, int]] = None) -> DrawImage:
        """Create a `DrawImage` object from an image url

        Args:
            _url_ -> URL of an image file.
            _size_ -> See class description.
        """
        if not isinstance(url, str):
            raise TypeError(f"URL must be a string, got {type(url).__name__!r}.")
        parsed_url = urlparse(url)
        if not any((parsed_url.scheme, parsed_url.netloc)):
            raise ValueError(f"Invalid url: {url!r}")

        response = requests.get(url, stream=True)
        if response.status_code == 404:
            raise FileNotFoundError(f"URL {url!r} does not exist.")

        basedir = os.path.join(os.path.expanduser("~"), ".terminal_image")
        if not os.path.isdir(basedir):
            os.mkdir(basedir)
        filepath = os.path.join(basedir, os.path.basename(urlparse(url).path))
        with open(filepath, "wb") as image_writer:
            image_writer.write(response.content)

        new = cls(Image.new("P", (0, 0)), size)
        new.__source = filepath
        return new

    @staticmethod
    def __validate_size(size: Optional[Tuple[int, int]]) -> None:
        """Check validity of an input for the size attribute"""
        if not (
            size is None
            or (
                isinstance(size, tuple)
                and len(size) == 2
                and all(isinstance(x, int) for x in size)
            )
        ):
            raise TypeError("'size' is expected to be tuple of two integers.")
