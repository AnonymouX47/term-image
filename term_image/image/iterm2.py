from __future__ import annotations

__all__ = ("ITerm2Image",)

import io
import re
import sys
import warnings
from base64 import standard_b64encode
from operator import mul
from threading import Event
from typing import Any, Dict, Optional, Set, Union

import PIL

from .. import TermImageWarning
from ..exceptions import _style_error
from ..utils import get_terminal_size, lock_tty, query_terminal, read_tty
from .common import GraphicsImage, ImageSource

FORMAT_SPEC = re.compile(r"([^LWNm]*)([LWN])?(m[01])?(.*)", re.ASCII)
# Constants for render methods
LINES = "lines"
WHOLE = "whole"


class ITerm2Image(GraphicsImage):
    """A render style using the iTerm2 inline image protocol.

    See :py:class:`GraphicsImage` for the complete description of the constructor.

    **Render Methods:**

    :py:class:`ITerm2Image` provides two methods of :term:`rendering` images, namely:

    lines (default)
       Renders an image line-by-line i.e the image is evenly split across the number
       of lines it should occupy.

       Pros:

         * Good for use cases where it might be required to trim some lines of the
           image.

       Cons:

         * Image drawing is very slow on iTerm2 due to the terminal emulator's
           performance.

    whole
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
        The **lines** method is the default only because it works properly in all cases,
        it's more advisable to use the **whole** method except when the image height is
        greater than the terminal height or when trimming the image is required.

    The render method can be set with
    :py:meth:`set_render_method() <BaseImage.set_render_method>` using the names
    specified above.


    **Format Specification**

    See :ref:`format-spec`.

    ::

        [method] [ m {0 | 1} ]

    * ``method``: Render method override.

      Can be one of:

        * ``L``: **lines** render method (current frame only, for animated images).
        * ``W``: **whole** render method (current frame only, for animated images).
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


    ATTENTION:
        Currently supported terminal emulators include:

          * `iTerm2 <https://iterm2.com>`_
          * `Konsole <https://konsole.kde.org>`_ >= 22.04.0
          * `WezTerm <https://wezfurlong.org/wezterm/>`_
    """

    #: Maximum size (in bytes) of image data for native animation.
    #:
    #: | :py:class:`TermImageWarning<term_image.TermImageWarning>` is issued
    #:   (and shown **only the first time**, except a filter is set to do otherwise)
    #:   if the image data size for a native animation is above this value.
    #: | This value can be altered but should be done with caution to avoid excessive
    #:   memory usage.
    NATIVE_ANIM_MAXSIZE = 2 * 2**20

    _render_methods: Set[str] = {LINES, WHOLE}
    _default_render_method: str = LINES
    _render_method: str = LINES
    _style_args = {
        "method": (
            (
                lambda x: isinstance(x, str),
                "Render method must be a string",
            ),
            (
                lambda x: x in ITerm2Image._render_methods,
                "Unknown render method",
            ),
        ),
        "mix": (
            (
                lambda x: isinstance(x, bool),
                "Cell content inter-mix policy must be a boolean",
            ),
            (lambda _: True, ""),
        ),
        "native": (
            (
                lambda x: isinstance(x, bool),
                "Native animation policy must be a boolean",
            ),
            (lambda _: True, ""),
        ),
        "stall_native": (
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
        mix: bool = False,
        native: bool = False,
        stall_native: bool = True,
        **kwargs,
    ):
        """Draws an image to standard output.

        Extends the common interface with style-specific parameters.

        Args:
            args: Positional arguments passed up the inheritance chain.
            mix: Cell content inter-mix policy (**Only supported in WezTerm**, ignored
              otherwise). If:

              * ``False``, contents of cells within the region covered by the image are
                erased.
              * ``True``, the opposite, thereby allowing existing text or image pixels
                to show under transparent areas of the image.

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
            # Terminal name/version query + terminal attribute query
            # The latter is to speed up the entirequery since most (if not all)
            # terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                b"\033[>q\033[c", lambda s: not s.endswith(b"\033[?6")
            ).decode()
            read_tty()  # The rest of the response to `CSI c`

            # Not supported if the terminal doesn't respond to either query
            # or responds to the second but not the first
            if response:
                match = re.fullmatch(
                    r"\033P>\|(\w+)[( ]([^\033]+)\)?\033\\",
                    response.rpartition("\033")[0],
                )
                if match and match.group(1).lower() in {"iterm2", "konsole", "wezterm"}:
                    name, version = map(str.lower, match.groups())
                    try:
                        if name == "konsole" and (
                            tuple(map(int, version.split("."))) < (22, 4, 0)
                        ):
                            cls._supported = False
                        else:
                            cls._supported = True
                            cls._TERM, cls._TERM_VERSION = name, version
                    except ValueError:  # version string not "understood"
                        cls._supported = False
            else:
                cls._supported = False

        return cls._supported

    @classmethod
    def _check_style_format_spec(cls, spec: str, original: str) -> Dict[str, Any]:
        parent, method, mix, invalid = FORMAT_SPEC.fullmatch(spec).groups()
        if invalid:
            raise _style_error(cls)(
                f"Invalid style-specific format specification {original!r}"
            )

        args = {}
        if parent:
            args.update(super()._check_style_format_spec(parent, original))
        if mix:
            args["mix"] = bool(int(mix[-1]))
        if method == "N":
            args["native"] = True
        elif method:
            args["method"] = LINES if method == "L" else WHOLE

        return cls._check_style_args(args)

    @classmethod
    def _clear_images(cls):
        if cls._TERM == "konsole":
            # Only works and required on Konsole, as text doesn't overwrite image cells.
            # Seems Konsole utilizes the same image rendering implementation as it
            # uses for the kiity graphics protocol.
            _stdout_write(b"\033_Ga=d;\033\\")
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
                erase_and_jump = f"\033[{r_width}X\033[{r_width}C"
                first_frame = self._format_render(
                    f"{erase_and_jump}\n" * (lines - 1) + f"{erase_and_jump}", *fmt
                )
                print(first_frame, f"\r\033[{lines - 1}A", sep="", end="", flush=True)

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
        jump_right = f"\033[{r_width}C"
        erase = f"\033[{r_width}X" if not mix and is_on_wezterm else ""

        file_is_readable = True
        if self._source_type is ImageSource.PIL_IMAGE:
            try:
                img.filename
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
                        f"\033[{r_height - 1}A",
                        "\033]1337;File=",
                        control_data,
                        standard_b64encode(compressed_image.read()).decode(),
                        ST,
                    )
                )

        render_method = method or self._render_method
        width, height = self._get_minimal_render_size()

        if (  # Read directly from file when possible and reasonable
            not self._is_animated
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
        else:
            img = self._get_render_data(
                img, alpha, size=(width, height), pixel_data=False  # fmt: skip
            )[0]
            format = "jpeg" if img.mode == "RGB" else "png"
            if render_method == LINES:
                raw_image = io.BytesIO(img.tobytes())
                compressed_image = io.BytesIO()
            else:
                compressed_image = io.BytesIO()
                img.save(compressed_image, format, quality=95)  # *quality* for JPEG

        # clean up
        if img is not self._source:
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
                        # *quality* for JPEG
                        img.save(compressed_image, format, quality=95)

                    is_on_wezterm and buffer.write(erase)
                    buffer.write(f"\033]1337;File=size={compressed_image.tell()}")
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
                    "" if is_on_konsole else f"\033[{r_height - 1}A",
                    "\033]1337;File=",
                    control_data,
                    standard_b64encode(compressed_image.read()).decode(),
                    ST,
                    f"{jump_right}\n" * (r_height - 1) if is_on_konsole else "",
                    jump_right * is_on_konsole,
                )
            )


ST = "\033\\"
native_anim = Event()
_stdout_write = sys.stdout.buffer.write
