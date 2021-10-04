import os
import requests
import time

from PIL import Image, GifImagePlugin
from typing import Optional, Tuple
from colr import Colr
from urllib.parse import urlparse, ParseResult


class DrawImage(object):
    PIXEL: str = "\u2584"

    @staticmethod
    def __validate_input(
        source: str, size: Optional[Tuple[int, int]], source_type: str = ""
    ):
        if source_type == "url":
            parsed_url: ParseResult = urlparse(source)
            if not any((parsed_url.scheme, parsed_url.netloc)):
                raise ValueError(f"Invalid url: {source}")
        elif not os.path.isfile(source):
            raise FileNotFoundError(f"{source} not found")

        if not (
            size is None
            or (isinstance(size, tuple) and all(isinstance(x, int) for x in size))
        ):
            raise TypeError("'size' is expected to be tuple of integers.")

    def __init__(self, filename: str, size: Optional[tuple] = (24, 24)):
        self.__filename = filename
        self.size = None if size == None else tuple(size)

        DrawImage.__validate_input(self.__filename, self.size, "file")

    def __display_gif(self, image: GifImagePlugin.GifImageFile) -> None:
        frame_filename = os.path.join(
            os.path.dirname(self.__filename),
            f"{os.path.basename(self.__filename)}-frames",
        )
        for frame in range(0, image.n_frames):
            image.seek(frame)
            image.save(frame_filename + f"{frame}.png")
            draw = DrawImage(frame_filename + f"{frame}.png", self.size)
            draw.draw_image()
            try:
                time.sleep(0.1)
            except KeyboardInterrupt:
                return
        self.__display_gif(image)

    def draw_image(self) -> None:
        """Print an image to the screen

        This function creates an Image objects, reads the colour
        of each pixel and print pixels with colours
        """
        image = Image.open(self.__filename, "r").convert("RGB")
        resized_images = image.resize(self.size) if self.size else image
        pixel_values = resized_images.getdata()

        if isinstance(image, GifImagePlugin.GifImageFile):
            self.__display_gif(image)
            return

        width, height = resized_images.size
        for index, character in enumerate(pixel_values):
            if not isinstance(character, (tuple, list)):
                continue
            r, g, b = character if len(character) == 3 else character[:-1]
            if index % width == 0:
                print("")
            print(
                self.__colored(r, g, b, self.PIXEL),
                end="\n" if index + 1 == len(pixel_values) else "",
            )

    def __colored(self: int, red: int, green: int, blue: int, text: str) -> str:
        return Colr().rgb(red, green, blue, text)

    @staticmethod
    def from_url(url: str, size: Optional[tuple] = (24, 24)):
        """Create a DrawImage object from an image url

        Write the raw response into an image file, create a new DraeImage object
        with the new file and return the object
        """
        DrawImage.__validate_input(url, size, "url")
        response = requests.get(url, stream=True)

        basedir = os.path.join(os.path.expanduser("~"), ".terminal_image")
        if not os.path.isdir(basedir):
            os.mkdir(basedir)
        filename = os.path.join(basedir, os.path.basename(urlparse(url).path))
        with open(filename, "wb") as image_writer:
            image_writer.write(response.content)
        return DrawImage(filename, size=size)
