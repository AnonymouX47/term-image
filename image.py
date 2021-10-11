import io
import os
import requests
import time

from PIL import Image, GifImagePlugin
from typing import Optional, Tuple
from urllib.parse import urlparse


class DrawImage(object):
    PIXEL: str = "\u2584"

    def __init__(self, image: Image.Image, size: Optional[Tuple[int, int]] = (24, 24)):
        if not isinstance(image, Image.Image):
            raise TypeError(
                "Expected a 'PIL.Image.Image' instance for 'image',"
                f" got {type(image).__name__!r}."
            )
        self.__validate_size(size)

        self.__source = image.convert("RGB")
        self.__buffer = io.StringIO()
        self.size = size

    def __display_gif(self, image: GifImagePlugin.GifImageFile):
        try:
            while True:
                for frame in range(0, image.n_frames):
                    image.seek(frame)
                    print(self.__draw_image(image))
                    self.__buffer.truncate()  # Clear buffer
                    time.sleep(0.1)
                    # Move cursor up to the first line of the image
                    print(f"\033[{image.size[1]}A", end="")
        except KeyboardInterrupt as e:
            # Move the cursor to line atfer the image and reset foreground color
            # Prevents "overlayed" and wrongly colored output on the terminal
            print(f"\033[{self.size[1]}B\033[0m")
            raise e from None

    def draw_image(self):
        """Print an image to the screen

        This function creates an Image object, reads the colour
        of each pixel and prints the pixels with their colours
        """
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

    def __draw_image(self, image: Image.Image):
        if self.size:
            image = image.resize(self.size)
        pixel_values = image.convert("RGB").getdata()
        width, _ = image.size

        # Characters for consecutive pixels of the same color, on the same row
        # are color-coded once
        n = 0
        cluster_pixel = pixel_values[0]

        buffer = self.__buffer  # Local variables have faster lookup times
        for index, pixel in enumerate(pixel_values):
            # Color-code characters and write to buffer when pixel color changes
            # or at the end of a row of pixels
            if pixel != cluster_pixel or index % width == 0:
                buffer.write(self.__colored(*cluster_pixel, self.PIXEL * n))
                if index and index % width == 0:
                    buffer.write("\n")
                n = 0
                cluster_pixel = pixel
            n += 1
        # Last cluster + color reset code.
        buffer.write(self.__colored(*cluster_pixel, self.PIXEL * n) + "\033[0m")

        buffer.seek(0)  # Reset buffer pointer
        return buffer.getvalue()

    @staticmethod
    def __colored(red: int, green: int, blue: int, text: str) -> str:
        return f"\033[38;2;{red};{green};{blue}m{text}"

    @classmethod
    def from_file(cls, filepath: str, size: Optional[tuple] = None):
        """Create a `DrawImage` object from an image file"""
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
    def from_url(cls, url: str, size: Optional[tuple] = None):
        """Create a DrawImage object from an image url

        Write the raw response into an image file, create a new DraeImage object
        with the new file and return the object.
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
