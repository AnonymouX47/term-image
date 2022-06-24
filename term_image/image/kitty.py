from __future__ import annotations

__all__ = ("KittyImage",)

import io
import re
import sys
from base64 import standard_b64encode
from dataclasses import asdict, dataclass
from typing import Any, Dict, Generator, Optional, Set, Tuple, Union
from zlib import compress, decompress

import PIL

from ..utils import CSI, ESC, ST, lock_tty, query_terminal
from .common import GraphicsImage

# Constants for render methods
LINES = "lines"
WHOLE = "whole"


class KittyImage(GraphicsImage):
    """A render style using the Kitty terminal graphics protocol.

    See :py:class:`GraphicsImage` for the complete description of the constructor.

    **Render Methods**

    :py:class:`KittyImage` provides two methods of :term:`rendering` images, namely:

    LINES (default)
       Renders an image line-by-line i.e the image is evenly split across the number
       of lines it should occupy.

       Pros:

         * Good for use cases where it might be required to trim some lines of the
           image.

    WHOLE
       Renders an image all at once i.e the entire image data is encoded into one
       line of the :term:`rendered` output, such that the entire image is drawn once
       by the terminal and still occupies the correct amount of lines and columns.

       Pros:

         * Render results are more compact (i.e less in character count) than with
           the **LINES** method since the entire image is encoded at once.

    The render method can be set with
    :py:meth:`set_render_method() <BaseImage.set_render_method>` using the names
    specified above.


    **Format Specification**

    See :ref:`format-spec`.

    ::

        [method] [ z [index] ] [ m {0 | 1} ] [ c {0-9} ]

    * ``method``: Render method override.

      Can be one of:

        * ``L``: **LINES** render method (current frame only, for animated images).
        * ``W``: **WHOLE** render method (current frame only, for animated images).

      Default: Current effective render method of the image.

    * ``z``: Image/Text stacking order.

      * ``index``: Image z-index. An integer in the **signed 32-bit range**.

        Images drawn in the same location with different z-index values will be
        blended if they are semi-transparent. If ``index`` is:

        * ``>= 0``, the image will be drawn above text.
        * ``< 0``, the image will be drawn below text.
        * ``< -(2**31)/2``, the image will be drawn below cells with non-default
          background color.

      * ``z`` without ``index`` is currently only used internally.
      * If *absent*, defaults to ``z0`` i.e z-index zero.
      * e.g ``z0``, ``z1``, ``z-1``, ``z2147483647``, ``z-2147483648``.

    * ``m``: Image/Text inter-mixing policy.

      * If the character after ``m`` is:

        * ``0``, text within the region covered by the image will be erased,
          though text can be inter-mixed with the image after it's been drawn.
        * ``1``, text within the region covered by the image will NOT be erased.

      * If *absent*, defaults to ``m0``.
      * e.g ``m0``, ``m1``.

    * ``c``: ZLIB compression level.

      * 1 -> best speed, 9 -> best compression, 0 -> no compression.
      * This results in a trade-off between render time and data size/draw speed.
      * If *absent*, defaults to ``c4``.
      * e.g ``c0``, ``c9``.


    ATTENTION:
        Currently supported terminal emulators include:

          * `Kitty <https://sw.kovidgoyal.net/kitty/>`_ >= 0.20.0.
          * `Konsole <https://konsole.kde.org>`_ >= 22.04.0.
    """

    _FORMAT_SPEC: Tuple[re.Pattern] = tuple(
        map(re.compile, r"[LW] z(-?\d+)? m[01] c[0-9]".split(" "))
    )
    _render_methods: Set[str] = {LINES, WHOLE}
    _default_render_method: str = LINES
    _render_method: str = LINES
    _style_args = {
        "method": (
            None,
            (
                lambda x: isinstance(x, str),
                "Render method must be a string",
            ),
            (
                lambda x: x.lower() in __class__._render_methods,
                "Unknown render method for 'kitty' render style",
            ),
        ),
        "z_index": (
            0,
            (
                lambda x: x is None or isinstance(x, int),
                "z-index must be `None` or an integer",
            ),
            (
                lambda x: x is None or -(2**31) <= x < 2**31,
                "z-index must be within the 32-bit signed integer range",
            ),
        ),
        "mix": (
            False,
            (
                lambda x: isinstance(x, bool),
                "Inter-mixing policy must be a boolean",
            ),
            (lambda _: True, ""),
        ),
        "compress": (
            4,
            (
                lambda x: isinstance(x, int),
                "Compression level must be an integer",
            ),
            (
                lambda x: 0 <= x <= 9,
                "Compression level must be between 0 and 9, both inclusive",
            ),
        ),
    }

    _KITTY_VERSION: Tuple[int, int, int] = ()
    _KONSOLE_VERSION: Tuple[int, int, int] = ()

    # Only defined for the purpose of proper self-documentation
    def draw(
        self,
        *args,
        method: Optional[str] = None,
        z_index: Optional[int] = 0,
        mix: bool = False,
        compress: int = 4,
        **kwargs,
    ) -> None:
        """Draws an image to standard output.

        Extends the common interface with style-specific parameters.

        Args:
            args: Positional arguments passed up the inheritance chain.
            method: Render method override. If ``None`` or not given, the current
              effective render method of the instance is used.
            z_index: The stacking order of images and text **for non-animations**.

              Images drawn in the same location with different z-index values will be
              blended if they are semi-transparent. If *z_index* is:

              * ``>= 0``, the image will be drawn above text.
              * ``< 0``, the image will be drawn below text.
              * ``< -(2**31)/2``, the image will be drawn below cells with
                non-default background color.
              * ``None``, internal use only, mentioned for the sake of completeness.

              To inter-mixing text with an image, see the *mix* parameter.

            mix: Image/Text inter-mixing policy **for non-animations**. If:

              * ``True``, text within the region covered by the image will NOT be
                erased.
              * ``False``, text within the region covered by the image will be
                erased, though text can be inter-mixed with the image after it's
                been drawn.

            compress: ZLIB compression level.

              An integer between 0 and 9: 1 -> best speed, 9 -> best compression, 0 ->
              no compression. This results in a trade-off between render time and data
              size/draw speed.

            kwargs: Keyword arguments passed up the inheritance chain.

        See the ``draw()`` method of the parent classes for full details, including the
        description of other parameters.
        """
        arguments = locals()
        super().draw(
            *args,
            **kwargs,
            **{
                var: arguments[var]
                for var, default in __class__.draw.__kwdefaults__.items()
                if arguments[var] is not default
            },
        )

    @classmethod
    @lock_tty
    def is_supported(cls):
        if cls._supported is None:
            cls._supported = False

            # Kitty graphics query + terminal attribute query
            # The second query is to speed up the query since most (if not all)
            # terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                (
                    f"{START}a=q,t=d,i=31,f=24,s=1,v=1,C=1,c=1,r=1;AAAA{ST}{CSI}c"
                ).encode(),
                lambda s: not s.endswith(b"c"),
            )

            # Not supported if it doesn't respond to either query
            # or responds to the second but not the first
            if response and (
                response.decode().rpartition(ESC)[0] == f"{START}i=31;OK{ST}"
            ):
                # Currently, only kitty >= 0.20.0 and Konsole >= 22.04.0 implement the
                # protocol features utilized
                response = query_terminal(
                    f"{CSI}>q".encode(), lambda s: not s.endswith(ST.encode())
                ).decode()  # Can not be `None` since the previous query was successful
                match = re.match(
                    r"\033P>\|(\w+)[( ]?([^)\033]+)\)?\033\\", response, re.ASCII
                )
                if match:
                    name, version = match.groups()
                    try:
                        version = tuple(map(int, version.split(".")))
                    except ValueError:  # Version string not "understood"
                        pass
                    else:
                        if name.lower() == "kitty":
                            cls._KITTY_VERSION = version
                        elif name.lower() == "konsole":
                            cls._KONSOLE_VERSION = version

                        # fmt: off
                        cls._supported = (
                            cls._KITTY_VERSION >= (0, 20, 0)
                            or cls._KONSOLE_VERSION >= (22, 4, 0)
                        )
                        # fmt: on

        return cls._supported

    @classmethod
    def _check_style_format_spec(cls, spec: str, original: str) -> Dict[str, Any]:
        parent, (method, (z, index), mix, compress) = cls._get_style_format_spec(
            spec, original
        )
        args = {}
        if parent:
            args.update(super()._check_style_format_spec(parent, original))
        if method:
            args["method"] = LINES if method == "L" else WHOLE
        if z:
            args["z_index"] = index and int(index)
        if mix:
            args["mix"] = bool(int(mix[-1]))
        if compress:
            args["compress"] = int(compress[-1])

        return cls._check_style_args(args)

    @staticmethod
    def _clear_images():
        _stdout_write(DELETE_ALL_IMAGES)
        return True

    @classmethod
    def _clear_frame(cls):
        if cls._KITTY_VERSION and cls._KITTY_VERSION <= (0, 25, 0):
            cls._clear_images()
            return True
        return False

    def _display_animated(self, *args, **kwargs) -> None:
        if self._KITTY_VERSION > (0, 25, 0):
            kwargs["z_index"] = None
        else:
            try:
                del kwargs["z_index"]
            except KeyError:
                pass

        super()._display_animated(*args, **kwargs)

    @staticmethod
    def _handle_interrupted_draw():
        """Performs neccessary actions when image drawing is interrupted.

        If drawing is interruped while transmiting a command, it causes terminal to
        wait for more data (in fact, it actually consumes any output following)
        until the output reaches the expected payload size or ST (String Terminator)
        is written.

        Also, if the image data was chunked, it would be expecting the last chunk.
        In this case, output is not consumed but the next graphics command sent
        might not be treated as expected on some terminals e.g Konsole.
        """

        # End last command (does no harm if there wasn't an unterminated commanand)
        # and send "last chunk" in case the last transmission was chunked.
        # Konsole sometimes requires ST to be written twice.
        print(f"{ST * 2}{START}q=1,m=0;{ST}", end="", flush=True)

    def _render_image(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        frame: bool = False,
        method: Optional[str] = None,
        z_index: Optional[int] = 0,
        mix: bool = False,
        compress: int = 4,
    ) -> str:
        # NOTE: It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        # Using `c` and `r` ensures that an image always occupies the correct amount
        # of columns and lines even if the cell size has changed when it's drawn.
        # Since we use `c` and `r` control data keys, there's no need upscaling the
        # image on this end; ensures minimal payload.

        render_method = (method or self._render_method).lower()
        r_width, r_height = self.rendered_size
        width, height = self._get_minimal_render_size(adjust=render_method == LINES)

        frame_img = img if frame else None
        img = self._get_render_data(
            img, alpha, size=(width, height), pixel_data=False, frame=frame  # fmt: skip
        )[0]
        format = getattr(f, img.mode)
        raw_image = img.tobytes()

        # clean up (ImageIterator uses one PIL image throughout)
        if frame_img is not img is not self._source:
            img.close()

        control_data = ControlData(f=format, s=width, c=r_width, z=z_index)
        erase = "" if mix else f"{CSI}{r_width}X"
        jump_right = f"{CSI}{r_width}C"
        if z_index is None:
            delete = f"{START}a=d,d=C;{ST}"

        if render_method == LINES:
            cell_height = height // r_height
            bytes_per_line = width * cell_height * (format // 8)
            vars(control_data).update(dict(v=cell_height, r=1))

            with io.StringIO() as buffer, io.BytesIO(raw_image) as raw_image:
                trans = Transmission(
                    control_data, raw_image.read(bytes_per_line), compress
                )
                z_index is None and buffer.write(delete)
                for chunk in trans.get_chunks():
                    buffer.write(chunk)
                # Writing spaces clears any text under transparent areas of an image
                for _ in range(r_height - 1):
                    buffer.write(erase)
                    buffer.write(jump_right)
                    buffer.write("\n")
                    trans = Transmission(
                        control_data, raw_image.read(bytes_per_line), compress
                    )
                    z_index is None and buffer.write(delete)
                    for chunk in trans.get_chunks():
                        buffer.write(chunk)
                buffer.write(erase)
                buffer.write(jump_right)

                return buffer.getvalue()
        else:
            vars(control_data).update(dict(v=height, r=r_height))
            return "".join(
                (
                    z_index is None and delete or "",
                    Transmission(control_data, raw_image, compress).get_chunked(),
                    f"{erase}{jump_right}\n" * (r_height - 1),
                    f"{erase}{jump_right}",
                )
            )


@dataclass
class Transmission:
    """An abstraction of the kitty terminal graphics escape code.

    Args:
        control: The control data.
        payload: The payload.
        level: Compression level.
    """

    control: ControlData
    payload: bytes

    # From tests with a few images, from anything beyond 4, the decrease in size
    # doesn't seem to be worth the increase in compression time in most cases.
    # Might change if proven otherwise.
    level: int = 4

    def __post_init__(self):
        self._compressed = False
        if self.level:
            self.compress()
        else:
            self.control.o = None

    def compress(self):
        if self.control.t == t.DIRECT and not self._compressed and self.level:
            self.payload = compress(self.payload, self.level)
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
        yield f"{START}{self.get_control_data()},m={bool(next_chunk):d};{chunk}{ST}"

        chunk, next_chunk = next_chunk, payload.read(size)
        while next_chunk:
            yield f"{START}m=1;{chunk}{ST}"
            chunk, next_chunk = next_chunk, payload.read(size)

        if chunk:  # false if there was never a next chunk
            yield f"{START}m=0;{chunk}{ST}"

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
    o: Optional[str] = None  # compression
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


START = f"{ESC}_G"
FMT = f"{START}%(control)s;%(payload)s{ST}"
DELETE_ALL_IMAGES = f"{ESC}_Ga=d;{ST}".encode()
_stdout_write = sys.stdout.buffer.write
