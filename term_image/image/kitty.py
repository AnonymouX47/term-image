from __future__ import annotations

__all__ = ("KittyImage",)

import io
from base64 import standard_b64encode
from dataclasses import asdict, dataclass
from math import ceil
from operator import mul
from typing import Generator, Optional, Tuple, Union
from zlib import compress, decompress

import PIL

from ..exceptions import TermImageException
from ..utils import get_cell_size, query_terminal
from .common import BaseImage


class KittyImage(BaseImage):
    """An image based on the Kitty terminal graphics protocol.

    Raises:
        term_image.exceptions.TermImageException: The :term:`active terminal` doesn't
          support the protocol.

    See :py:class:`BaseImage` for the complete description of the constructor.
    """

    _pixel_ratio = 1.0  # Size unit conversion already involves cell size calculation

    def __init__(self, image: PIL.Image.Image, **kwargs) -> None:
        if not self.is_supported():
            raise TermImageException(
                "This image render style is not supported in the current terminal"
            )
        super().__init__(image, **kwargs)

    @classmethod
    def is_supported(cls):
        if cls._supported is None:
            # Kitty graphics query + terminal attribute query
            # The second query is to speed up the query since most (if not all)
            # terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                b"\033_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\033\\\033[c",
                lambda s: not s.endswith(b"c"),
            )
            # Not supported if it doesn't respond to either query
            # or responds to the second but not the first
            cls._supported = bool(response and response.rpartition(b"\033")[0])

        return cls._supported

    def _get_render_size(self) -> Tuple[int, int]:
        return tuple(map(mul, self.rendered_size, get_cell_size() or (1, 2)))

    @staticmethod
    def _pixels_cols(
        *, pixels: Optional[int] = None, cols: Optional[int] = None
    ) -> int:
        return (
            ceil(pixels // (get_cell_size() or (1, 2))[0])
            if pixels is not None
            else cols * (get_cell_size() or (1, 2))[0]
        )

    @staticmethod
    def _pixels_lines(
        *, pixels: Optional[int] = None, lines: Optional[int] = None
    ) -> int:
        return (
            ceil(pixels // (get_cell_size() or (1, 2))[1])
            if pixels is not None
            else lines * (get_cell_size() or (1, 2))[1]
        )

    def _render_image(
        self, img: PIL.Image.Image, alpha: Union[None, float, str]
    ) -> str:
        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        buffer = io.StringIO()
        # Eliminate attribute resolution cost
        buf_write = buffer.write

        img = self._get_render_data(img, alpha)[0]
        format = getattr(f, img.mode)
        raw_image = io.BytesIO(img.tobytes())

        # clean up
        if img is not self._source:
            img.close()

        width, height = self._get_render_size()
        cell_height = get_cell_size()[1]
        pixels_per_line = width * cell_height * (format // 8)
        control_data = ControlData(f=format, s=width, v=cell_height)

        with buffer, raw_image:
            trans = Transmission(control_data, raw_image.read(pixels_per_line))
            buf_write(trans.get_chunked())
            for _ in range(self.rendered_height - 1):
                buf_write("\n")
                trans = Transmission(control_data, raw_image.read(pixels_per_line))
                buf_write(trans.get_chunked())

            return buffer.getvalue()


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
    C: Optional[int] = C.STAY  # cursor movement policy
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
