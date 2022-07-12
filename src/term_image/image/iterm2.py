from __future__ import annotations

__all__ = ("ITerm2Image",)

import io
import re
import sys
import warnings
from base64 import standard_b64encode
from operator import mul
from threading import Event
from typing import Any, Dict, Optional, Set, Tuple, Union

import PIL

from .. import TermImageWarning
from ..exceptions import _style_error
from ..utils import (
    CSI,
    ESC,
    OSC,
    ST,
    get_terminal_size,
    lock_tty,
    query_terminal,
    read_tty,
)
from .common import GraphicsImage, ImageSource

# Constants for render methods
LINES = "lines"
WHOLE = "whole"


class ITerm2Image(GraphicsImage):
    """A render style using the iTerm2 inline image protocol.

    See :py:class:`GraphicsImage` for the complete description of the constructor.

    **Render Methods:**

    :py:class:`ITerm2Image` provides two methods of :term:`rendering` images, namely:

    LINES (default)
       Renders an image line-by-line i.e the image is evenly split across the number
       of lines it should occupy.

       Pros:

         * Good for use cases where it might be required to trim some lines of the
           image.

       Cons:

         * Image drawing is very slow on iTerm2 due to the terminal emulator's
           performance.

    WHOLE
       Renders an image all at once i.e the entire image data is encoded into one
       line of the :term:`rendered` output, such that the entire image is drawn once
       by the terminal and still occupies the correct amount of lines and columns.

       Pros:

         * Render results are more compact (i.e less in character count) than with
           the ``lines`` method since the entire image is encoded at once.
         * Image drawing is faster than with ``lines`` on most terminals.
         * Smoother animations.

       Cons:

          * This method currently doesn't work well on iTerm2 and WezTerm when the image
            height is greater than the terminal height.

    NOTE:
        The **LINES** method is the default only because it works properly in all cases,
        it's more advisable to use the **WHOLE** method except when the image height is
        greater than the terminal height or when trimming the image is required.

    The render method can be set with
    :py:meth:`set_render_method() <BaseImage.set_render_method>` using the names
    specified above.


    **Format Specification**

    See :ref:`format-spec`.

    ::

        [method] [ m {0 | 1} ] [ c {0-9} ]

    * ``method``: Render method override.

      Can be one of:

        * ``L``: **LINES** render method (current frame only, for animated images).
        * ``W``: **WHOLE** render method (current frame only, for animated images).
        * ``N``: Native animation. Ignored when used with non-animated images, WEBP
          images or ``ImageIterator``.

      Default: Current effective render method of the image.

    * ``m``: Cell content inter-mix policy (**Only supported in WezTerm**, ignored
      otherwise).

      * If the character after ``m`` is:

        * ``0``, contents of cells in the region covered by the image will be erased.
        * ``1``, the opposite, thereby allowing existing cell contents to show under
          transparent areas of the image.

      * If *absent*, defaults to ``m0``.
      * e.g ``m0``, ``m1``.

    * ``c``: ZLIB compression level, for images re-encoded in PNG format.

      * 1 -> best speed, 9 -> best compression, 0 -> no compression.
      * This results in a trade-off between render time and data size/draw speed.
      * If *absent*, defaults to ``c4``.
      * e.g ``c0``, ``c9``.


    ATTENTION:
        Currently supported terminal emulators include:

          * `iTerm2 <https://iterm2.com>`_
          * `Konsole <https://konsole.kde.org>`_ >= 22.04.0
          * `WezTerm <https://wezfurlong.org/wezterm/>`_
    """

    #: * ``x < 0``, JPEG encoding is disabled.
    #: * ``0 <= x <= 95``, JPEG encoding is used, with the specified quality, for
    #:   **most** non-transparent renders (at the cost of image quality).
    #:
    #: Only applies when not reading directly from file.
    #:
    #: By default, images are encoded in the PNG format (when not reading directly
    #: from file) but in some cases, higher compression might be desired.
    #: Also, JPEG encoding is significantly faster and can be useful to improve
    #: non-native animation performance.
    #:
    #: .. hint:: The transparency status of some images can not be correctly determined
    #:   in an efficient way at render time. To ensure the JPEG format is always used
    #:   for a re-encoded render, disable transparency or set a background color.
    JPEG_QUALITY: int = -1

    #: Maximum size (in bytes) of image data for native animation.
    #:
    #: | :py:class:`TermImageWarning<term_image.TermImageWarning>` is issued
    #:   (and shown **only the first time**, except a filter is set to do otherwise)
    #:   if the image data size for a native animation is above this value.
    #: | This value can be altered but should be done with caution to avoid excessive
    #:   memory usage.
    NATIVE_ANIM_MAXSIZE: int = 2 * 2**20  # 2 MiB

    #: * ``True``, image data is read directly from file when possible and no image
    #:   manipulation is required.
    #: * ``False``, images are always loaded and re-encoded, in the PNG format by
    #:   default.
    #:
    #: This is an optimization to reduce render times and is only applicable to the
    #: **WHOLE** render method, since the the **LINES** method inherently requires
    #: image manipulation.
    #:
    #: .. note:: This setting does not affect animations, native animations are always
    #:   read from file when possible and frames of non-native animations have to be
    #:   loaded and re-encoded.
    READ_FROM_FILE: bool = True

    _FORMAT_SPEC: Tuple[re.Pattern] = tuple(
        map(re.compile, "[LWN] m[01] c[0-9]".split(" "))
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
                "Unknown render method for 'iterm2' render style",
            ),
        ),
        "mix": (
            False,
            (
                lambda x: isinstance(x, bool),
                "Cell content inter-mix policy must be a boolean",
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
        "native": (
            False,
            (
                lambda x: isinstance(x, bool),
                "Native animation policy must be a boolean",
            ),
            (lambda _: True, ""),
        ),
        "stall_native": (
            True,
            (
                lambda x: isinstance(x, bool),
                "Native animation execution policy must be a boolean",
            ),
            (lambda _: True, ""),
        ),
    }

    _TERM: str = ""
    _TERM_VERSION: str = ""

    def draw(
        self,
        *args,
        method: Optional[str] = None,
        mix: bool = False,
        compress: int = 4,
        native: bool = False,
        stall_native: bool = True,
        **kwargs,
    ):
        """Draws an image to standard output.

        Extends the common interface with style-specific parameters.

        Args:
            args: Positional arguments passed up the inheritance chain.
            method: Render method override. If ``None`` or not given, the current
              effective render method of the instance is used.
            mix: Cell content inter-mix policy (**Only supported in WezTerm**, ignored
              otherwise). If:

              * ``False``, contents of cells within the region covered by the image are
                erased.
              * ``True``, the opposite, thereby allowing existing text or image pixels
                to show under transparent areas of the image.

            compress: ZLIB compression level, for images re-encoded in PNG format.

              An integer between 0 and 9: 1 -> best speed, 9 -> best compression, 0 ->
              no compression. This results in a trade-off between render time and data
              size/draw speed.

            native: If ``True``, use native animation (if supported).

              * Ignored for non-animations.
              * *animate* must be ``True``.
              * *alpha*, *repeat*, *cached* and *style* do not apply.
              * Always loops infinitely.
              * No control over frame duration.
              * Not all animated image formats are supported e.g WEBP.
              * The limitations of the **WHOLE** render method also apply.
              * Normal restrictions for rendered/padding height of animations do not
                apply.

            stall_native: Native animation execution control. If:

              * ``True``, block until ``SIGINT`` (Ctrl+C) is recieved.
              * ``False``, return as soon as the image is transmitted.

            kwargs: Keyword arguments passed up the inheritance chain.

        Raises:
            term_image.exceptions.ITerm2ImageError: Native animation is not supported.

        See the ``draw()`` method of the parent classes for full details, including the
        description of other parameters.
        """
        if not (self._is_animated and kwargs.get("animate", True)):
            # Prevent the arguments from being passed on
            native = False
            stall_native = True

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
    @lock_tty  # the terminal's response to the query is not read all at once
    def is_supported(cls):
        if cls._supported is None:
            cls._supported = False
            # Terminal name/version query + terminal attribute query
            # The latter is to speed up the entire query since most (if not all)
            # terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                f"{CSI}>q{CSI}c".encode(), lambda s: not s.endswith(CSI.encode())
            )
            read_tty()  # The rest of the response to `CSI c`

            # Not supported if the terminal doesn't respond to either query
            # or responds to the second but not the first
            if response:
                match = re.fullmatch(
                    r"\033P>\|(\w+)[( ]([^\033]+)\)?\033\\",
                    response.decode().rpartition(ESC)[0],
                )
                if match and match.group(1).lower() in {"iterm2", "konsole", "wezterm"}:
                    name, version = map(str.lower, match.groups())
                    try:
                        if name != "konsole" or (
                            tuple(map(int, version.split("."))) >= (22, 4, 0)
                        ):
                            cls._supported = True
                            cls._TERM, cls._TERM_VERSION = name, version
                    except ValueError:  # version string not "understood"
                        pass

        return cls._supported

    @classmethod
    def _check_style_format_spec(cls, spec: str, original: str) -> Dict[str, Any]:
        parent, (method, mix, compress) = cls._get_style_format_spec(spec, original)
        args = {}
        if parent:
            args.update(super()._check_style_format_spec(parent, original))
        if method == "N":
            args["native"] = True
        elif method:
            args["method"] = LINES if method == "L" else WHOLE
        if mix:
            args["mix"] = bool(int(mix[-1]))
        if compress:
            args["compress"] = int(compress[-1])

        return cls._check_style_args(args)

    @classmethod
    def _clear_images(cls):
        if cls._TERM == "konsole":
            # Only works and required on Konsole, as text doesn't overwrite image cells.
            # Seems Konsole utilizes the same image rendering implementation as it
            # uses for the kiity graphics protocol.
            _stdout_write(DELETE_ALL_IMAGES)
            return True
        return False

    def _display_animated(
        self,
        img,
        alpha,
        fmt,
        *args,
        mix: bool = False,
        native: bool = False,
        stall_native: bool = True,
        **kwargs,
    ):
        if native:
            if self._TERM == "konsole":
                raise _style_error(type(self))(
                    "Native animation is not supported in the active terminal"
                )
            if img.format == "WEBP":
                raise _style_error(type(self))("Native WEBP animation is not supported")
            try:
                print(
                    self._format_render(
                        self._render_image(img, alpha, mix=mix, native=True),
                        *fmt,
                    ),
                    end="",
                    flush=True,
                )
            except (KeyboardInterrupt, Exception):
                self._handle_interrupted_draw()
                raise
            else:
                stall_native and native_anim.wait()
        else:
            if not mix and self._TERM == "wezterm":
                lines = max(
                    (fmt or (None,))[-1] or get_terminal_size()[1] - self._v_allow,
                    self.rendered_height,
                )
                r_width = self.rendered_width
                erase_and_jump = f"{CSI}{r_width}X{CSI}{r_width}C"
                first_frame = self._format_render(
                    f"{erase_and_jump}\n" * (lines - 1) + f"{erase_and_jump}", *fmt
                )
                print(first_frame, f"\r{CSI}{lines - 1}A", sep="", end="", flush=True)

            super()._display_animated(img, alpha, fmt, *args, mix=True, **kwargs)

    @staticmethod
    def _handle_interrupted_draw():
        """Performs neccessary actions when image drawing is interrupted.

        If drawing is interruped while transmiting an image, it causes terminal to
        wait for more data (while consuming any output following) until the output
        reaches the expected payload size or ST (String Terminator) is written.
        """

        # End last transmission (does no harm if there wasn't an unterminated
        # transmission)
        # Konsole sometimes requires ST to be written twice.
        print(f"{ST * 2}", end="", flush=True)

    def _render_image(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        frame: bool = False,
        method: Optional[str] = None,
        mix: bool = False,
        compress: int = 4,
        native: bool = False,
    ) -> str:
        # Using `width=<columns>`, `height=<lines>` and `preserveAspectRatio=0` ensures
        # that an image always occupies the correct amount of columns and lines even if
        # the cell size has changed when it's drawn.
        # Since we use `width` and `height` control data keys, there's no need
        # upscaling an image on this end; ensures minimal payload.

        r_width, r_height = self.rendered_size

        # Workarounds
        is_on_konsole = self._TERM == "konsole"
        is_on_wezterm = self._TERM == "wezterm"
        jump_right = f"{CSI}{r_width}C"
        erase = f"{CSI}{r_width}X" if not mix and is_on_wezterm else ""

        file_is_readable = True
        if self._source_type is ImageSource.PIL_IMAGE:
            try:
                open(img.filename)
            except (AttributeError, OSError):
                file_is_readable = False

        if native and self._is_animated and not frame and img.format != "WEBP":
            if self._source_type is ImageSource.PIL_IMAGE:
                if file_is_readable:
                    compressed_image = open(img.filename, "rb")
                else:
                    try:
                        compressed_image = io.BytesIO()
                        img.save(compressed_image, img.format, save_all=True)
                    except ValueError:
                        raise _style_error(type(self))(
                            "Native animation not supported: This image was sourced "
                            "from a PIL image of an unknown format"
                        ) from None
            else:
                compressed_image = open(self._source, "rb")

            if img is not self._source:
                img.close()

            with compressed_image:
                compressed_image.seek(0, 2)
                if compressed_image.tell() > __class__.NATIVE_ANIM_MAXSIZE:
                    warnings.warn(
                        "Image data size above the maximum for native animation",
                        TermImageWarning,
                    )

                control_data = "".join(
                    (
                        f"size={compressed_image.tell()};width={r_width}"
                        f";height={r_height};preserveAspectRatio=0;inline=1:"
                    )
                )
                compressed_image.seek(0)
                return "".join(
                    (
                        f"{erase}{jump_right}\n" * (r_height - 1),
                        erase,
                        f"{CSI}{r_height - 1}A",
                        START,
                        control_data,
                        standard_b64encode(compressed_image.read()).decode(),
                        ST,
                    )
                )

        render_method = (method or self._render_method).lower()
        width, height = self._get_minimal_render_size(adjust=render_method == LINES)

        if (  # Read directly from file when possible and reasonable
            self.READ_FROM_FILE
            and not self._is_animated
            and file_is_readable
            and render_method == WHOLE
            and mul(*self._original_size) <= mul(*self._get_render_size())
            and (
                # None of the *alpha* options can affect these
                img.mode in {"1", "L", "RGB", "HSV", "CMYK"}
                # Alpha threshold is unused with graphics-based styles.
                # The transparency of some "P" mode images is missing on some terminals
                # Making the output inconsistent with other render styles.
                or (isinstance(alpha, float) and img.mode not in {"P", "PA"})
            )
        ):
            compressed_image = open(
                img.filename
                if self._source_type is ImageSource.PIL_IMAGE
                else self._source,
                "rb",
            )
            frame_img = None
        else:
            frame_img = img if frame else None
            img = self._get_render_data(
                img, alpha, size=(width, height), pixel_data=False, frame=frame
            )[0]  # fmt: skip
            if self.JPEG_QUALITY >= 0 and img.mode == "RGB":
                format = "jpeg"
                jpeg_quality = min(self.JPEG_QUALITY, 95)
            else:
                format = "png"
                jpeg_quality = None

            if render_method == LINES:
                raw_image = io.BytesIO(img.tobytes())
                compressed_image = io.BytesIO()
            else:
                compressed_image = io.BytesIO()
                img.save(
                    compressed_image,
                    format,
                    compress_level=compress,  # PNG
                    quality=jpeg_quality,
                )

        # clean up (ImageIterator uses one PIL image throughout)
        if frame_img is not img is not self._source:
            img.close()

        if render_method == LINES:
            # NOTE: It's more efficient to write separate strings to the buffer
            # separately than concatenate and write together.

            cell_height = height // r_height
            bytes_per_line = width * cell_height * (len(img.mode))
            control_data = (
                f";width={r_width};height=1;preserveAspectRatio=0;inline=1"
                f"{';doNotMoveCursor=1' * is_on_konsole}:"
            )

            with io.StringIO() as buffer, raw_image, compressed_image:
                for line in range(1, r_height + 1):
                    compressed_image.seek(0)
                    compressed_image.truncate()
                    with PIL.Image.frombytes(
                        img.mode, (width, cell_height), raw_image.read(bytes_per_line)
                    ) as img:
                        img.save(
                            compressed_image,
                            format,
                            compress_level=compress,  # PNG
                            quality=jpeg_quality,
                        )

                    buffer.write(erase)
                    buffer.write(f"{START}size={compressed_image.tell()}")
                    buffer.write(control_data)
                    buffer.write(
                        standard_b64encode(compressed_image.getvalue()).decode()
                    )
                    buffer.write(ST)
                    is_on_konsole and buffer.write(jump_right)
                    line < r_height and buffer.write("\n")

                return buffer.getvalue()

        # WHOLE
        with compressed_image:
            compressed_image.seek(0, 2)
            control_data = "".join(
                (
                    f"size={compressed_image.tell()};width={r_width}"
                    f";height={r_height};preserveAspectRatio=0;inline=1"
                    f"{';doNotMoveCursor=1' * is_on_konsole}:"
                )
            )
            compressed_image.seek(0)
            return "".join(
                (
                    "" if is_on_konsole else f"{erase}{jump_right}\n" * (r_height - 1),
                    erase,
                    "" if is_on_konsole else f"{CSI}{r_height - 1}A",
                    START,
                    control_data,
                    standard_b64encode(compressed_image.read()).decode(),
                    ST,
                    f"{jump_right}\n" * (r_height - 1) if is_on_konsole else "",
                    jump_right * is_on_konsole,
                )
            )


START = f"{OSC}1337;File="
DELETE_ALL_IMAGES = f"{ESC}_Ga=d;{ST}".encode()
native_anim = Event()
_stdout_write = sys.stdout.buffer.write
