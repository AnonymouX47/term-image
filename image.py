import os
import requests
import shutil

from PIL import Image
from typing import Optional


class DrawImage(object):
    PIXEL = "\u2584"

    def __init__(
        self, filename: str, size: Optional[tuple] = (24, 24), draw: bool = True
    ):
        self.__filename = filename
        self.size = None if size == None else tuple(size)

        if not os.path.isfile(self.__filename):
            raise FileNotFoundError(f"{self.__filename} not found")

        if draw:
            self.draw_image()

    def draw_image(self) -> None:
        """Print an image to the screen

        This function creates an Image objects, reads the colour
        of each pixel and print pixels with colours
        """
        image = Image.open(self.__filename, "r")
        resized_images = image.resize(self.size) if self.size else image
        pixel_values = resized_images.getdata()

        width, height = resized_images.size
        for index, character in enumerate(pixel_values):
            if not isinstance(character, (tuple, list)):
                continue
            r, g, b = character if len(character) == 3 else character[:-1]
            if index % width == 0:
                print("")
            print(self.__colored(r, g, b, self.PIXEL), end="")

    def __colored(self: int, red: int, green: int, blue: int, text: str) -> str:
        return "\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(
            red, green, blue, text
        )

    @staticmethod
    def from_url(
        url: str, size: Optional[tuple] = (24, 24), draw: bool = True
    ) -> DrawImage:
        """Create a DrawImage object from an image url

        Write the raw response into an image file, create a new DraeImage object
        with the new file and return the object
        """
        response = requests.get(url, stream=True)

        basedir = os.path.join(os.path.expanduser("~"), ".terminal_image")
        if not os.path.isdir(basedir):
            os.mkdir(basedir)
        filename = os.path.join(basedir, os.path.basename(url))
        with open(filename, "wb") as image_writer:
            shutil.copyfileobj(response.raw, image_writer)
        return DrawImage(filename, size=size, draw=draw)
