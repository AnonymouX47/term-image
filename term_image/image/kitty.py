from __future__ import annotations

__all__ = ("KittyImage",)

import io
import os
import sys
from base64 import standard_b64encode
from dataclasses import asdict, dataclass
from subprocess import run
from typing import Generator, Optional, Set, Union
from zlib import compress, decompress

import PIL

from ..utils import lock_tty, query_terminal
from .common import GraphicsImage

# Constants for ``KittyImage`` render method
LINES = "lines"
WHOLE = "whole"


class KittyImage(GraphicsImage):
    """A render style using the Kitty terminal graphics protocol.

    See :py:class:`GraphicsImage` for the complete description of the constructor.

    **Render Methods:**

    :py:class:`KittyImage` provides two methods of :term:`rendering` images, namely:

    lines
       Renders an image line-by-line i.e the image if evenly split up across
       the number of line it should occupy and all portions is joined together by
       ``\\n`` (newline sequence) to give the whole image.

       Pros:

         * Good for use cases where it might be required to trim some lines of the
           image.

    whole
       Renders an image all at once i.e the entire image data is encoded into the first
       line of the :term:`rendered` output, such that the entire image is drawn once
       by the terminal and still occupies the proper amount of lines and columns.

       Pros:

         * Render results are less in number of characters compared to the
           ``lines`` method since the entire image is encoded at once.
         * Better for non-animated images that are large in resolution and pixel
           density as images are drawn once.

    The render method can be set with
    :py:meth:`set_render_method() <BaseImage.set_render_method>` using the names
    specified above.

    ATTENTION:
        Currently supported terminal emulators include:

          * `Kitty <https://sw.kovidgoyal.net/kitty/>`_ >= 0.20.0.
          * `Konsole <https://konsole.kde.org>`_ >= 22.04.0.
    """

    _render_methods: Set[str] = {LINES, WHOLE}
    _default_render_method: str = LINES
    _render_method: str = LINES

    @classmethod
    @lock_tty
    def is_supported(cls):
        if cls._supported is None:
            # Kitty graphics query + terminal attribute query
            # The second query is to speed up the query since most (if not all)
            # terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                (
                    f"{_START}a=q,t=d,i=31,f=24,s=1,v=1,C=1,c=1,r=1;AAAA{_END}\033[c"
                ).encode(),
                lambda s: not s.endswith(b"c"),
            )
            # Not supported if it doesn't respond to either query
            # or responds to the second but not the first
            cls._supported = response and (
                response.rpartition(b"\033")[0] == f"{_START}i=31;OK{_END}".encode()
            )

            # Currently, only kitty >= 0.20.0 and Konsole 22.04.0 implement the
            # protocol features utilized
            if cls._supported:
                result = run(
                    "kitty +kitten query-terminal --wait-for=0.1 name version",
                    shell=True,
                    text=True,
                    capture_output=True,
                )
                name, version = map(
                    lambda query: query.partition(" ")[2], result.stdout.split("\n", 1)
                )

                cls._supported = (
                    not result.returncode
                    and name == "xterm-kitty"
                    and tuple(map(int, version.split("."))) >= (0, 20, 0)
                    or int(os.environ.get("KONSOLE_VERSION", "0")) >= 220400
                )

        return cls._supported

    @staticmethod
    def _clear_images():
        _stdout_write(b"\033_Ga=d;\033\\")
        return True

    _clear_frame = _clear_images

    def _render_image(
        self, img: PIL.Image.Image, alpha: Union[None, float, str]
    ) -> str:
        # Using `c` and `r` ensures that an image always occupies the correct amount
        # of columns and lines even if the cell size has changed when it's drawn.
        # Since we use `c` and `r` control data keys, there's no need upscaling the
        # image on this end; ensures minimal payload.

        r_width, r_height = self.rendered_size
        width, height = self._get_minimal_render_size()

        img = self._get_render_data(img, alpha, size=(width, height))[0]
        format = getattr(f, img.mode)
        raw_image = img.tobytes()

        # clean up
        if img is not self._source:
            img.close()

        return getattr(self, f"_render_image_{self._render_method}")(
            raw_image, format, width, height, r_width, r_height
        )

    @staticmethod
    def _render_image_lines(
        raw_image: bytes,
        format: int,
        width: int,
        height: int,
        r_width: int,
        r_height: int,
    ) -> str:
        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        cell_height = height // r_height
        bytes_per_line = width * cell_height * (format // 8)

        with io.StringIO() as buffer, io.BytesIO(raw_image) as raw_image:
            control_data = ControlData(f=format, s=width, v=cell_height, c=r_width, r=1)
            trans = Transmission(control_data, raw_image.read(bytes_per_line))
            fill = " " * r_width

            buffer.write(trans.get_chunked())
            # Writing spaces clears any text under transparent areas of an image
            for _ in range(r_height - 1):
                buffer.write(fill + "\n")
                trans = Transmission(control_data, raw_image.read(bytes_per_line))
                buffer.write(trans.get_chunked())
            buffer.write(fill)

            return buffer.getvalue()

    @staticmethod
    def _render_image_whole(
        raw_image: bytes,
        format: int,
        width: int,
        height: int,
        r_width: int,
        r_height: int,
    ) -> str:
        return (
            Transmission(
                ControlData(f=format, s=width, v=height, c=r_width, r=r_height),
                raw_image,
            ).get_chunked()
            + (" " * r_width + "\n") * (r_height - 1)
            + " " * r_width
        )


@dataclass
class Transmission:
    """An abstraction of the kitty terminal graphics escape code.

    Args:
        control: The control data.
        payload: The payload.
    """

    control: ControlData
    payload: bytes

    def __post_init__(self):
        self._compressed = False
        if self.control.o == o.ZLIB:
            self.compress()

    def compress(self):
        if self.control.t == t.DIRECT and not self._compressed:
            self.payload = compress(self.payload)
            self.control.o = o.ZLIB
            self._compressed = True

    def decompress(self):
        if self.control.t == t.DIRECT and self._compressed:
            self.control.o = None
            self.payload = decompress(self.payload)
            self._compressed = False

    def encode(self) -> bytes:
        return standard_b64encode(self.payload)

    def get_chunked(self) -> str:
        return "".join(self.get_chunks())

    def get_chunks(self, size: int = 4096) -> Generator[str, None, None]:
        payload = self.get_payload()

        chunk, next_chunk = payload.read(size), payload.read(size)
        yield f"\033_G{self.get_control_data()},m={bool(next_chunk):d};{chunk}\033\\"

        chunk, next_chunk = next_chunk, payload.read(size)
        while next_chunk:
            yield f"\033_Gm=1;{chunk}\033\\"
            chunk, next_chunk = next_chunk, payload.read(size)

        if chunk:  # false if there was never a next chunk
            yield f"\033_Gm=0;{chunk}\033\\"

    def get_control_data(self) -> str:
        return ",".join(
            f"{key}={value}"
            for key, value in asdict(self.control).items()
            if value is not None
        )

    def get_payload(self) -> io.StringIO:
        return io.StringIO(self.encode().decode("ascii"))


# Values for control data keys with limited set of values


class a:
    TRANS = "t"
    TRANS_DISP = "T"
    QUERY = "q"
    PLACE = "p"
    DELETE = "d"
    TRANS_FRAMES = "f"
    CONTROL_ANIM = "a"
    COMPOSE_FRAMES = "c"


class C:
    MOVE = 0
    STAY = 1


class f:
    RGB = 24
    RGBA = 32
    PNG = 100


class o:
    ZLIB = "z"


class t:
    DIRECT = "d"
    FILE = "f"
    TEMP = "t"
    SHARED = "s"


class z:
    BEHIND = -1
    IN_FRONT = 0


@dataclass
class ControlData:
    """Represents a portion of the kitty terminal graphics protocol control data"""

    a: Optional[str] = a.TRANS_DISP  # action
    f: Optional[int] = f.RGBA  # data format
    t: Optional[str] = t.DIRECT  # transmission medium
    s: Optional[int] = None  # image width
    v: Optional[int] = None  # image height
    z: Optional[int] = z.IN_FRONT  # z-index
    o: Optional[str] = o.ZLIB  # compression
    C: Optional[int] = C.STAY  # cursor movement policy

    # # Image display size in columns and rows/lines
    # # The image is shrunk or enlarged to fit
    c: Optional[int] = None  # columns
    r: Optional[int] = None  # rows

    def __post_init__(self):
        if self.f == f.PNG:
            self.s = self.v = None


class _ControlData:  # Currently Unused

    i: Optional[int] = None  # image ID
    d: Optional[str] = None  # delete images
    m: Optional[int] = None  # payload chunk
    O: Optional[int] = None  # data start offset; with t=s or t=f
    S: Optional[int] = None  # data size in bytes; with f=100,o=z or t=s or t=f

    # Origin offset (px) within the current cell; Must be less than the cell size
    # (0, 0) == Top-left corner of the cell; Not used with `c` and `r`.
    X: Optional[int] = None
    Y: Optional[int] = None

    # Image crop (px)
    # # crop origin; (0, 0) == top-left corner of the image
    x: Optional[int] = None
    y: Optional[int] = None
    # # crop rectangle size
    w: Optional[int] = None
    h: Optional[int] = None


_START = "\033_G"
_END = "\033\\"
_FMT = f"{_START}%(control)s;%(payload)s{_END}"
_stdout_write = sys.stdout.buffer.write
