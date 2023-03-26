from __future__ import annotations

__all__ = ("ITerm2Image",)

import io
import os
import re
import sys
import warnings
from base64 import standard_b64encode
from operator import mul
from threading import Event
from typing import Any, Dict, Optional, Set, Tuple, Union

import PIL

from ..exceptions import TermImageWarning, _style_error
from ..utils import (
    CSI,
    OSC,
    ST,
    ClassInstanceProperty,
    ClassProperty,
    get_terminal_name_version,
    get_terminal_size,
    write_tty,
)
from .common import GraphicsImage, ImageSource
from .kitty import (
    DELETE_ALL_IMAGES,
    DELETE_CURSOR_IMAGES,
    DELETE_ALL_IMAGES_b,
    DELETE_CURSOR_IMAGES_b,
)

# Constants for render methods
LINES = "lines"
WHOLE = "whole"


class ITerm2Image(GraphicsImage):
    """A render style using the iTerm2 inline image protocol.

    See :py:class:`GraphicsImage` for the complete description of the constructor.

    |

    **Render Methods**

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
         the **LINES** method since the entire image is encoded at once.
       * Image drawing is faster than with **LINES** on most terminals.
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

    |

    **Style-Specific Render Parameters**

    See :py:meth:`BaseImage.draw` (particularly the *style* parameter).

    * **method** (*None | str*) → Render method override.

      * ``None`` → the current effective render method of the instance is used.
      * *default* → ``None``

    * **mix** (*bool*) → Cell content inter-mix policy (**Only supported on WezTerm**,
      ignored otherwise).

      * ``False`` → existing contents of cells within the region covered by
        the drawn render output are erased
      * ``True`` → existing cell contents show under transparent areas of the
        drawn render output
      * *default* → ``False``

    * **compress** (*int*) → ZLIB compression level, for renders re-encoded in PNG
      format.

      * ``0`` <= *compress* <= ``9``
      * ``1`` → best speed, ``9`` → best compression, ``0`` → no compression
      * *default* → ``4``
      * Results in a trade-off between render time and data size/draw speed

    * **native** (*bool*) → Native animation policy. [1]_

      * ``True`` → use the protocol's native animation feature
      * ``False`` → use the normal animation
      * *default* → ``False``
      * *alpha*, *repeat*, *cached* and *style* do not apply
      * Ignored if the image is not animated or *animate* is ``False``
      * Normal restrictions for sizing of animations do not apply
      * Uses **WHOLE** render method
      * The terminal emulator completely controls the animation

    * **stall_native** (*bool*) → Native animation execution control.

      * ``True`` → block until ``SIGINT`` (Ctrl+C) is recieved
      * ``False`` → return as soon as the image is transmitted
      * *default* → ``True``

    |

    **Format Specification**

    See :ref:`format-spec`.

    ::

        [ <method> ]  [ m <mix> ]  [ c <compress> ]

    * ``method`` → render method override

      * ``L`` → **LINES** render method (current frame only, for animated images)
      * ``W`` → **WHOLE** render method (current frame only, for animated images)
      * ``N`` → Native animation [1]_ (ignored when used with non-animated images or
        :py:class:`~term_image.image.ImageIterator`)
      * *default* → current effective render method of the instance

    * ``m`` → cell content inter-mix policy (**Only supported in WezTerm**, ignored
      otherwise)

      * ``mix`` → inter-mix policy

        * ``0`` → existing contents of cells in the region covered by the drawn
          render output will be erased
        * ``1`` → existing cell contents show under transparent areas of the drawn
          render output

      * *default* → ``m0``
      * e.g ``m0``, ``m1``

    * ``c`` → ZLIB compression level, for renders re-encoded in PNG format

      * ``compress`` → compression level

        * An integer in the range ``0`` <= ``x`` <= ``9``
        * ``1`` → best speed, ``9`` → best compression, ``0`` → no compression

      * *default* → ``c4``
      * e.g ``c0``, ``c9``
      * Results in a trade-off between render time and data size/draw speed

    |

    IMPORTANT:
        Currently supported terminal emulators are:

        * `iTerm2 <https://iterm2.com>`_
        * `Konsole <https://konsole.kde.org>`_ >= 22.04.0
        * `WezTerm <https://wezfurlong.org/wezterm/>`_

    .. [1] Native animation support:

       * Not all animated image formats may be supported by every supported terminal
         emulator
       * Not all supported terminal emulators implement this feature of the protocol
         e.g on Konsole, the first frame is drawn but the image is not animated

    |
    """

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

    jpeg_quality = ClassInstanceProperty(
        lambda self_or_cls: getattr(self_or_cls, "_jpeg_quality", -1),
        doc="""
        JPEG encoding quality

        :type: int

        GET:
            Returns the effective JPEG encoding quality of the invoker
            (negative if disabled).

        SET:
            If invoked via:

            * a **class**, the **class-wide** quality is set.
            * an **instance**, the **instance-specific** quality is set.

        DELETE:
            If invoked via:

            * a **class**, the **class-wide** quality is unset.
            * an **instance**, the **instance-specific** quality is unset.

        If:

        * *value* < ``0``; JPEG encoding is disabled.
        * ``0`` <= *value* <= ``95``; JPEG encoding is enabled with the given quality.

        If **unset** for:

        * a **class**, it uses that of its parent *iterm2* style class (if any) or the
          default (disabled), if unset for all parents or the class has no parent
          *iterm2* style class.
        * an **instance**, it uses that of it's class.

        By **default**, the quality is **unset** i.e JPEG encoding is **disabled** and
        images are encoded in the PNG format (when not reading directly from file) but
        in some cases, higher and/or faster compression may be desired.
        JPEG encoding is significantly faster than PNG encoding and produces smaller
        (in data size) output but **at the cost of image quality**.

        NOTE:
            * This property is :term:`descendant`.
            * This optimization applies to only **re-encoded** (i.e not read directly
              from file) **non-transparent** renders.

        TIP:
            The transparency status of some images can not be correctly determined
            in an efficient way at render time. To ensure JPEG encoding is always used
            for a re-encoded render, disable transparency or set a background color.

            Furthermore, to ensure that renders with the **WHOLE** :term:`render method`
            are always re-encoded, disable :py:attr:`read_from_file`.

            This optimization is useful in improving non-native animation performance.

        SEE ALSO:
            * the *alpha* parameter of :py:meth:`~term_image.image.BaseImage.draw`
              and the ``#``, ``bgcolor`` fields of the :ref:`format-spec`
            * :py:attr:`read_from_file`
        """,
    )

    @jpeg_quality.setter
    def jpeg_quality(self_or_cls, quality: int) -> None:
        if not isinstance(quality, int):
            raise TypeError(
                f"Invalid type for 'quality' (got: {type(quality).__name__})"
            )
        if quality > 95:
            raise ValueError(f"'quality' out of range (got: {quality})")

        self_or_cls._jpeg_quality = quality

    @jpeg_quality.deleter
    def jpeg_quality(self_or_cls) -> None:
        try:
            del self_or_cls._jpeg_quality
        except AttributeError:
            pass

    native_anim_max_bytes = ClassProperty(
        # 2 MiB default
        lambda cls: getattr(__class__, "_native_anim_max_bytes", 2 * 2**20),
        doc="""
        Maximum size (in bytes) of image data for native animation

        :type: int

        GET:
            Returns the set value.

        SET:
            A positive integer; the value is set on the *iterm2* render style baseclass
            (:py:class:`ITerm2Image`).

        DELETE:
            The value is unset, thereby resetting it to the default.

        :py:class:`~term_image.exceptions.TermImageWarning` is issued (and shown
        **only the first time**, except a filter is set to do otherwise) if the
        image data size for a native animation is above this value.

        NOTE:
            This property is :term:`descendant` but is always unset for all subclasses
            and instances. Hence, setting/resetting it on this class, a subclass or an
            instance affects this class, all its subclasses and all their instances.

        WARNING:
            This property should be altered with caution to avoid excessive memory
            usage.
        """,
    )

    @native_anim_max_bytes.setter
    def native_anim_max_bytes(cls, max_bytes: int):
        if not isinstance(max_bytes, int):
            raise TypeError(
                f"Invalid type for 'max_bytes' (got: {type(max_bytes).__name__})"
            )
        if max_bytes <= 0:
            raise ValueError(f"'max_bytes' out of range (got: {max_bytes})")

        __class__._native_anim_max_bytes = max_bytes

    @native_anim_max_bytes.deleter
    def native_anim_max_bytes(cls):
        try:
            del __class__._native_anim_max_bytes
        except AttributeError:
            pass

    read_from_file = ClassInstanceProperty(
        lambda self_or_cls: getattr(self_or_cls, "_read_from_file", True),
        doc="""
        Read-from-file optimization policy

        :type: bool

        GET:
            Returns the effective read-from-file policy of the invoker.

        SET:
            If invoked via:

            * a **class**, the **class-wide** policy is set.
            * an **instance**, the **instance-specific** policy is set.

        DELETE:
            If invoked via:

            * a **class**, the **class-wide** policy is unset.
            * an **instance**, the **instance-specific** policy is unset.

        If the value is:

        * ``True``, image data is read directly from file when possible and no image
          manipulation is required.
        * ``False``, images are always re-encoded (in the PNG format by default).

        If **unset** for:

        * a **class**, it uses that of its parent *iterm2* style class (if any) or the
          default (``True``), if unset for all parents or the class has no parent
          *iterm2* style class.
        * an **instance**, it uses that of it's class.

        By **default**, the policy is **unset**, which is equivalent to ``True``
        i.e the optimization is **enabled**.

        NOTE:
            * This property is :term:`descendant`.
            * This is an optimization to reduce render times and is only applicable to
              the **WHOLE** render method, since the the **LINES** method inherently
              requires image manipulation.
            * This property does not affect animations. Native animations are always
              read from file when possible and frames of non-native animations have
              to be re-encoded.

        SEE ALSO:
            :py:attr:`jpeg_quality`
        """,
    )

    @read_from_file.setter
    def read_from_file(self_or_cls, policy: bool) -> None:
        if not isinstance(policy, bool):
            raise TypeError(f"Invalid type for 'policy' (got: {type(policy).__name__})")

        self_or_cls._read_from_file = policy

    @read_from_file.deleter
    def read_from_file(self_or_cls) -> None:
        try:
            del self_or_cls._read_from_file
        except AttributeError:
            pass

    @classmethod
    def clear(cls, cursor: bool = False, now: bool = False) -> None:
        """Clears images.

        Args:
            cursor: If ``True``, all images intersecting with the current cursor
              position are cleared. Otherwise, all visible images are cleared.
            now: If ``True`` the images are cleared immediately, without affecting
              any standard I/O stream.
              Otherwise they're cleared when next :py:data:`sys.stdout` is flushed.

        NOTE:
            Required and works only on Konsole, as text doesn't overwrite images.
        """
        # There's no point checking for forced support since this is only required on
        # konsole which supports the protocol.
        # `is_supported()` is first called to ensure `_TERM` has been set.
        if cls.is_supported() and cls._TERM == "konsole":
            # Konsole utilizes the same image rendering implementation as it
            # uses for the kiity graphics protocol.
            (write_tty if now else _stdout_write)(
                (DELETE_CURSOR_IMAGES_b if now else DELETE_CURSOR_IMAGES)
                if cursor
                else (DELETE_ALL_IMAGES_b if now else DELETE_ALL_IMAGES)
            )

    def draw(self, *args, **kwargs):
        # Ignore (and omit) native animation arguments for non-animations
        if not (self._is_animated and kwargs.get("animate", True)):
            for arg_name in ("native", "stall_native"):
                try:
                    del kwargs[arg_name]
                except KeyError:
                    pass

        super().draw(*args, **kwargs)

    @classmethod
    def is_supported(cls):
        if cls._supported is None:
            cls._supported = False

            name, version = get_terminal_name_version()
            if name in {"iterm2", "konsole", "wezterm"}:
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
        jump_up = f"{CSI}{r_height - 1}A" if r_height > 1 else ""
        erase = f"{CSI}{r_width}X" if not mix and is_on_wezterm else ""

        file_is_readable = True
        if self._source_type is ImageSource.PIL_IMAGE:
            try:
                file_is_readable = os.access(img.filename, os.R_OK)
            except (AttributeError, OSError):
                file_is_readable = False

        if native and self._is_animated and not frame:
            if self._source_type is ImageSource.PIL_IMAGE:
                if file_is_readable:
                    compressed_image = open(img.filename, "rb")
                else:
                    compressed_image = io.BytesIO()
                    try:
                        img.save(compressed_image, img.format, save_all=True)
                    except ValueError:
                        self._close_image(img)
                        raise _style_error(type(self))(
                            "Native animation not supported: This image was sourced "
                            "from a PIL image of an unknown format"
                        ) from None
            else:
                compressed_image = open(self._source, "rb")

            self._close_image(img)

            with compressed_image:
                compressed_image.seek(0, 2)
                if compressed_image.tell() > self.native_anim_max_bytes:
                    warnings.warn(
                        "Image data size above the maximum for native animation",
                        TermImageWarning,
                    )

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
                        (
                            ""
                            if is_on_konsole
                            else f"{erase}{jump_right}\n" * (r_height - 1)
                        ),
                        erase,
                        "" if is_on_konsole else jump_up,
                        START,
                        control_data,
                        standard_b64encode(compressed_image.read()).decode(),
                        ST,
                        f"{jump_right}\n" * (r_height - 1) if is_on_konsole else "",
                        jump_right * is_on_konsole,
                    )
                )

        render_method = (method or self._render_method).lower()
        width, height = self._get_minimal_render_size(adjust=render_method == LINES)

        if (  # Read directly from file when possible and reasonable
            self.read_from_file
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
            if self.jpeg_quality >= 0 and img.mode == "RGB":
                format = "jpeg"
                jpeg_quality = self.jpeg_quality
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
        if frame_img is not img:
            self._close_image(img)

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
                    with PIL.Image.frombytes(
                        img.mode, (width, cell_height), raw_image.read(bytes_per_line)
                    ) as img:
                        img.save(
                            compressed_image,
                            format,
                            compress_level=compress,  # PNG
                            quality=jpeg_quality,
                        )
                    compressed_image.truncate()

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
                    "" if is_on_konsole else jump_up,
                    START,
                    control_data,
                    standard_b64encode(compressed_image.read()).decode(),
                    ST,
                    f"{jump_right}\n" * (r_height - 1) if is_on_konsole else "",
                    jump_right * is_on_konsole,
                )
            )


START = f"{OSC}1337;File="
native_anim = Event()
_stdout_write = sys.stdout.write
