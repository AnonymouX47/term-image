import os
import requests
import shutil
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

    def __init__(self, filepath: str, size: Optional[Tuple[int, int]] = (24, 24)):
        DrawImage.__validate_input(filepath, size, "file")

        self.__filepath = filepath
        self.size = size

    def __display_gif(self, image: GifImagePlugin.GifImageFile):
        frame_dir = f"{self.__filepath}-frames"
        if not os.path.isdir(frame_dir):
            os.mkdir(frame_dir)
        try:
            for frame in range(0, image.n_frames):
                image.seek(frame)
                image.save(os.path.join(frame_dir, f"{frame}.png"))
            while True:
                for frame in range(0, image.n_frames):
                    DrawImage(
                        os.path.join(frame_dir, f"{frame}.png"),
                        self.size,
                    ).draw_image()
                    time.sleep(0.1)
                    print(f"\033[{self.size[1]}A", end="")
        except KeyboardInterrupt:
            print("\033[0m")
        finally:
            shutil.rmtree(frame_dir)

    def draw_image(self):
        """Print an image to the screen

        This function creates an Image object, reads the colour
        of each pixel and prints the pixels with their colours
        """
        image = Image.open(self.__filepath, "r")

        if isinstance(image, GifImagePlugin.GifImageFile):
            self.__display_gif(image)
            return

        if self.size:
            image = image.resize(self.size)
        pixel_values = image.convert("RGB").getdata()
        width, _ = image.size

        # Characters for consecutive pixels of the same color, on the same row
        # are color-coded once
        n = 0
        cluster_pixel = pixel_values[0]

        print("\033[1A", end="")  # Compensate for "\n" printed when index == 0

        canceled = False
        for index, pixel in enumerate(pixel_values):
            try:
                # Color-code and print characters when pixel color changes
                # or at the end of a row of pixels
                if pixel != cluster_pixel or index % width == 0:
                    print(
                        self.__colored(*cluster_pixel, self.PIXEL * n),
                        end="\n" * (not (index % width)),
                    )
                    n = 0
                    cluster_pixel = pixel
                n += 1
            # Disallow truncation of the image
            except KeyboardInterrupt as e:
                canceled = True
                err = e

        # Last cluster
        print(self.__colored(*cluster_pixel, self.PIXEL * n))

        if canceled:
            raise err

    def __colored(self: int, red: int, green: int, blue: int, text: str) -> str:
        return Colr().rgb(red, green, blue, text)

    @staticmethod
    def from_url(url: str, size: Optional[tuple] = (24, 24)):
        """Create a DrawImage object from an image url

        Write the raw response into an image file, create a new DraeImage object
        with the new file and return the object.
        """
        __class__.__validate_input(url, size, "url")
        response = requests.get(url, stream=True)
        if response.status_code == 404:
            raise FileNotFoundError(f"URL {url!r} does not exist.")

        basedir = os.path.join(os.path.expanduser("~"), ".terminal_image")
        if not os.path.isdir(basedir):
            os.mkdir(basedir)
        filepath = os.path.join(basedir, os.path.basename(urlparse(url).path))
        with open(filepath, "wb") as image_writer:
            image_writer.write(response.content)

        return __class__(filepath, size=size)
