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

from .. import ctlseqs

# These sequences are used during performance-critical operations that occur often
from ..ctlseqs import (
    CURSOR_FORWARD,
    ERASE_CHARS,
    KITTY_DELETE_CURSOR,
    KITTY_TRANSMISSION,
)
from ..utils import (
    arg_type_error,
    arg_value_error_msg,
    arg_value_error_range,
    get_terminal_name_version,
    query_terminal,
    write_tty,
)
from .common import GraphicsImage

# Constants for render methods
LINES = "lines"
WHOLE = "whole"


class KittyImage(GraphicsImage):
    """A render style using the Kitty terminal graphics protocol.

    See :py:class:`GraphicsImage` for the complete description of the constructor.

    |

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

    |

    **Style-Specific Render Parameters**

    See :py:meth:`BaseImage.draw` (particularly the *style* parameter).

    * **method** (*None | str*) → Render method override.

      * ``None`` → the current effective render method of the instance is used
      * A valid render method name (as specified in the **Render Methods** section
        above) → used instead of the current effective render method of the instance
      * *default* → ``None``

    * **z_index** (*int*) → The stacking order of graphics and text for
      **non-animations**.

      * An integer in the **signed 32-bit** range (excluding ``-(2**31)``)
      * ``>= 0`` → the image will be drawn above text
      * ``< 0`` → the image will be drawn below text
      * ``< -(2**31)/2`` → the image will be drawn below cells with non-default
        background color
      * *default* → ``0``
      * Overlapping graphics on different z-indexes will be blended (by the terminal
        emulator) if they are semi-transparent.
      * To inter-mix text with graphics, see the *mix* parameter.

    * **mix** (*bool*) → Graphics/Text inter-mix policy.

      * ``False`` → text within the region covered by the drawn render output will be
        erased, though text can be inter-mixed with graphics after drawing
      * ``True`` → text within the region covered by the drawn render output will NOT
        be erased
      * *default* → ``False``

    * **compress** (*int*) → ZLIB compression level.

      * ``0`` <= *compress* <= ``9``
      * ``1`` → best speed, ``9`` → best compression, ``0`` → no compression
      * *default* → ``4``
      * Results in a trade-off between render time and data size/draw speed

    |

    **Format Specification**

    See :ref:`format-spec`.

    ::

        [ <method> ]  [ z <z-index> ]  [ m <mix> ]  [ c <compress> ]

    * ``method`` → render method override

      * ``L`` → **LINES** render method (current frame only, for animated images)
      * ``W`` → **WHOLE** render method (current frame only, for animated images)
      * *default* → Current effective render method of the image

    * ``z`` → graphics/text stacking order

      * ``z-index`` → z-index

        * An integer in the **signed 32-bit** range (excluding ``-(2**31)``)
        * ``>= 0`` → the render output will be drawn above text
        * ``< 0`` → the render output will be drawn below text
        * ``< -(2**31)/2`` → the render output will be drawn below cells with
          non-default background color

      * *default* → ``z0`` (z-index zero)
      * e.g ``z0``, ``z1``, ``z-1``, ``z2147483647``, ``z-2147483648``
      * overlapping graphics on different z-indexes will be blended
        (by the terminal emulator) if they are semi-transparent

    * ``m`` → graphics/text inter-mix policy

      * ``mix`` → inter-mix policy

        * ``0`` → text within the region covered by the drawn render output will be
          erased, though text can be inter-mixed with graphics after drawing
        * ``1`` → text within the region covered by the drawn render output will NOT
          be erased

      * *default* → ``m0``
      * e.g ``m0``, ``m1``

    * ``c`` → ZLIB compression level

      * ``compress`` → compression level

        * An integer in the range ``0`` <= ``compress`` <= ``9``
        * ``1`` → best speed, ``9`` → best compression, ``0`` → no compression

      * *default* → ``c4``
      * e.g ``c0``, ``c9``
      * results in a trade-off between render time and data size/draw speed

    |

    IMPORTANT:
        Currently supported terminal emulators are:

        * `Kitty <https://sw.kovidgoyal.net/kitty/>`_ >= 0.20.0.
        * `Konsole <https://konsole.kde.org>`_ >= 22.04.0.
    """

    _FORMAT_SPEC: Tuple[re.Pattern] = tuple(
        map(re.compile, r"[LW] z-?\d+ m[01] c[0-9]".split(" "))
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
                lambda x: isinstance(x, int),
                "z-index must be an integer",
            ),
            (
                # INT32_MIN is reserved for non-native animations
                lambda x: -(2**31) < x < 2**31,
                "z-index must be within the 32-bit signed integer range "
                "(excluding ``-(2**31)``)",
            ),
        ),
        "mix": (
            False,
            (
                lambda x: isinstance(x, bool),
                "Inter-mix policy must be a boolean",
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

    _TERM: str = ""
    _TERM_VERSION: str = ""
    _KITTY_VERSION: Tuple[int, int, int] = ()

    @classmethod
    def clear(
        cls, *, cursor: bool = False, z_index: Optional[int] = None, now: bool = False
    ) -> None:
        """Clears images.

        Args:
            cursor: If ``True``, all images intersecting with the current cursor
              position are cleared.
            z_index: An integer in the **signed 32-bit range**. If given, all images
              on the given z-index are cleared.
            now: If ``True`` the images are cleared immediately, without affecting
              any standard I/O stream.
              Otherwise they're cleared when next :py:data:`sys.stdout` is flushed.

        Aside *now*, **only one** other argument may be given. If no argument is given
        (aside *now*) or default values are given, all images visible on the screen are
        cleared.

        NOTE:
            This method does nothing if the render style is not supported.
        """
        if not (cls._forced_support or cls.is_supported()):
            return

        if not isinstance(cursor, bool):
            raise arg_type_error("cursor", cursor)

        if z_index is not None:
            if not isinstance(z_index, int):
                raise arg_type_error("z_index", z_index)
            if not -(1 << 31) <= z_index < (1 << 31):
                raise arg_value_error_range("z_index", z_index)

        if not isinstance(now, bool):
            raise arg_type_error("now", now)

        default_args = __class__.clear.__func__.__kwdefaults__
        nonlocals = locals()
        args = {name: nonlocals[name] for name in default_args}
        given_args = args.items() - (default_args.items() | {("now", True)})

        if len(given_args) > 1:
            raise arg_value_error_msg(
                "Only one argument (aside 'now') may be given", len(given_args)
            )
        elif given_args:
            arg, _ = given_args.pop()
            (write_tty if now else _stdout_write)(
                (ctlseqs.KITTY_DELETE_CURSOR_b if now else ctlseqs.KITTY_DELETE_CURSOR)
                if arg == "cursor"
                else (
                    (
                        ctlseqs.KITTY_DELETE_Z_INDEX_b
                        if now
                        else ctlseqs.KITTY_DELETE_Z_INDEX
                    )
                    % z_index
                )
            )
        elif now:
            write_tty(ctlseqs.KITTY_DELETE_ALL_b)
        else:
            _stdout_write(ctlseqs.KITTY_DELETE_ALL)

    @classmethod
    def is_supported(cls) -> bool:
        if cls._supported is None:
            cls._supported = False

            # The graphics query for support detection messes up iTerm2's window title
            if get_terminal_name_version()[0] == "iterm2":
                return False

            # Kitty graphics query + terminal attribute query
            # The second query is to speed up the query since most (if not all)
            # terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                ctlseqs.KITTY_SUPPORT_QUERY_b + ctlseqs.DA1_b,
                lambda s: not s.endswith(b"c"),
            )

            # Not supported if it doesn't respond to either query
            # or responds to the second but not the first
            if response:
                response = ctlseqs.KITTY_RESPONSE_re.match(response.decode())
            if response and response["id"] == "31" and response["message"] == "OK":
                name, version = get_terminal_name_version()
                # Only kitty >= 0.20.0 implement the protocol features utilized
                if name == "kitty" and version:
                    try:
                        version_tuple = tuple(map(int, version.split(".")))
                    except ValueError:  # Version string not "understood"
                        pass
                    else:
                        if version_tuple >= (0, 20, 0):
                            cls._TERM, cls._TERM_VERSION = name, version
                            cls._KITTY_VERSION = version_tuple
                            cls._supported = True
                # Konsole is good as long as it responds to the graphics query
                elif name == "konsole":
                    cls._TERM, cls._TERM_VERSION = name, version or ""
                    cls._supported = True

        return cls._supported

    @classmethod
    def _check_style_format_spec(cls, spec: str, original: str) -> Dict[str, Any]:
        parent, (method, z_index, mix, compress) = cls._get_style_format_spec(
            spec, original
        )
        args = {}
        if parent:
            args.update(super()._check_style_format_spec(parent, original))
        if method:
            args["method"] = LINES if method == "L" else WHOLE
        if z_index:
            args["z_index"] = int(z_index[1:])
        if mix:
            args["mix"] = bool(int(mix[-1]))
        if compress:
            args["compress"] = int(compress[-1])

        return cls._check_style_args(args)

    @classmethod
    def _clear_frame(cls) -> bool:
        """Clears an animation frame on-screen.

        | Only used on Kitty <= 0.25.0 because ``blend=False`` is buggy on these
          versions. Does nothing on any other version or terminal.
        | Also clears any frame of any previously drawn animation, since they all use
          the same z-index.

        See :py:meth:`~term_image.image.BaseImage._clear_frame` for description.
        """
        if cls._KITTY_VERSION and cls._KITTY_VERSION <= (0, 25, 0):
            cls.clear(z_index=-(1 << 31))
            return True
        return False

    def _display_animated(self, *args, **kwargs) -> None:
        kwargs["z_index"] = -(1 << 31)
        if self._KITTY_VERSION > (0, 25, 0):
            kwargs["blend"] = False

        super()._display_animated(*args, **kwargs)

    @staticmethod
    def _handle_interrupted_draw():
        """Performs necessary actions when image drawing is interrupted.

        If drawing is interrupted while transmitting a command, it causes terminal to
        wait for more data (in fact, it actually consumes any output following)
        until the output reaches the expected payload size or ST (String Terminator)
        is written.

        Also, if the image data was chunked, it would be expecting the last chunk.
        In this case, output is not consumed but the next graphics command sent
        might not be treated as expected on some terminals e.g Konsole.
        """

        # End last command (does no harm if there wasn't an unterminated command)
        # and send "last chunk" in case the last transmission was chunked.
        # Konsole sometimes requires ST to be written twice.
        print(ctlseqs.ST * 2 + ctlseqs.KITTY_END_CHUNKED, end="", flush=True)

    def _render_image(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        frame: bool = False,
        method: Optional[str] = None,
        z_index: int = 0,
        mix: bool = False,
        compress: int = 4,
        blend: bool = True,
    ) -> str:
        """See :py:meth:`BaseImage._render_image` for the description of the method and
        :py:meth:`draw` for parameters not described here.

        Args:
            blend: If ``False``, the rendered image deletes overlapping/intersecting
              images when drawn. Otherwise, the behaviour is dependent on the z-index
              and/or the terminal emulator (for images with the same z-index).
        """
        # NOTE: It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        # Using `c` and `r` ensures that an image always occupies the correct amount
        # of columns and lines even if the cell size has changed when it's drawn.
        # Since we use `c` and `r` control data keys, there's no need upscaling the
        # image on this end to reduce payload.
        # Anyways, this also implies that the image(s) have to be resized by the
        # terminal emulator, thereby leaving various details of resizing in the hands
        # of the terminal emulator such as the resampling method, etc.
        # This particularly affects the LINES render method negatively, resulting in
        # slant/curved edges not lining up across lines (amongst other artifacts
        # observed on Konsole) supposedly because the terminal emulator resizes each
        # line separately.
        # Hence, this optimization is only used for the WHOLE render method.

        render_method = (method or self._render_method).lower()
        r_width, r_height = self.rendered_size
        width, height = (
            self._get_minimal_render_size()
            if render_method == WHOLE
            else self._get_render_size()
        )

        frame_img = img if frame else None
        img = self._get_render_data(
            img, alpha, size=(width, height), pixel_data=False, frame=frame  # fmt: skip
        )[0]
        format = getattr(f, img.mode)
        raw_image = img.tobytes()

        # clean up (ImageIterator uses one PIL image throughout)
        if frame_img is not img:
            self._close_image(img)

        control_data = ControlData(f=format, s=width, c=r_width, z=z_index)
        fill = ("" if mix else ERASE_CHARS % r_width) + (CURSOR_FORWARD % r_width)
        fill_newline = fill + "\n"

        if render_method == LINES:
            cell_height = height // r_height
            bytes_per_line = width * cell_height * (format // 8)
            vars(control_data).update(dict(v=cell_height, r=1))

            with io.StringIO() as buffer, io.BytesIO(raw_image) as raw_image:
                trans = Transmission(
                    control_data, raw_image.read(bytes_per_line), compress
                )
                blend or buffer.write(KITTY_DELETE_CURSOR)
                for chunk in trans.get_chunks():
                    buffer.write(chunk)
                for _ in range(r_height - 1):
                    buffer.write(fill_newline)
                    trans = Transmission(
                        control_data, raw_image.read(bytes_per_line), compress
                    )
                    blend or buffer.write(KITTY_DELETE_CURSOR)
                    for chunk in trans.get_chunks():
                        buffer.write(chunk)
                buffer.write(fill)

                return buffer.getvalue()

        vars(control_data).update(v=height, r=r_height)
        return "".join(
            (
                KITTY_DELETE_CURSOR * (not blend),
                Transmission(control_data, raw_image, compress).get_chunked(),
                fill_newline * (r_height - 1),
                fill,
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
        with self.get_payload() as payload:
            chunk, next_chunk = payload.read(size), payload.read(size)
            yield (
                KITTY_TRANSMISSION
                % (f"{self.get_control_data()},m={bool(next_chunk):d}", chunk)
            )

            chunk, next_chunk = next_chunk, payload.read(size)
            while next_chunk:
                yield KITTY_TRANSMISSION % ("m=1", chunk)
                chunk, next_chunk = next_chunk, payload.read(size)

            if chunk:  # false if there was never a next chunk
                yield KITTY_TRANSMISSION % ("m=0", chunk)

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


_stdout_write = sys.stdout.write
