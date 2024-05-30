from __future__ import annotations

__all__ = ("ITerm2Image",)

import io
import os
import re
import sys
import warnings
from base64 import standard_b64encode
from operator import mul
from typing import Any, Dict, Optional, Set, Tuple, Union

import PIL

from .. import ctlseqs

# These sequences are used during performance-critical operations that occur often
from ..ctlseqs import CURSOR_FORWARD, CURSOR_UP, ERASE_CHARS, ITERM2_START, ST
from ..exceptions import RenderError, TermImageWarning
from ..utils import (
    ClassInstanceProperty,
    ClassProperty,
    arg_type_error,
    arg_value_error_range,
    get_terminal_name_version,
    write_tty,
)
from .common import GraphicsImage, ImageMeta, ImageSource

# Constants for render methods
LINES = "lines"
WHOLE = "whole"
ANIM = "anim"


class ITerm2ImageMeta(ImageMeta):
    """Type of iterm2 render style classes."""

    __native_anim_max_bytes = _native_anim_max_bytes = 2 * 2**20  # 2 MiB default

    jpeg_quality = ClassInstanceProperty(
        lambda self: getattr(self, "_jpeg_quality", -1),
        doc="""JPEG encoding quality

        See the base instance of this metaclass for the complete description.
        """,
    )

    @jpeg_quality.setter
    def jpeg_quality(self, quality: int) -> None:
        if not isinstance(quality, int):
            raise arg_type_error("jpeg_quality", quality)
        if quality > 95:
            raise arg_value_error_range("jpeg_quality", quality)

        self._jpeg_quality = quality

    @jpeg_quality.deleter
    def jpeg_quality(self) -> None:
        try:
            del self._jpeg_quality
        except AttributeError:
            pass

    native_anim_max_bytes = ClassProperty(
        lambda self: __class__._native_anim_max_bytes,
        doc="""Maximum size (in bytes) of image data for native animation

        See the base instance of this metaclass for the complete description.
        """,
    )

    @native_anim_max_bytes.setter
    def native_anim_max_bytes(self, max_bytes: int):
        if not isinstance(max_bytes, int):
            raise arg_type_error("native_anim_max_bytes", max_bytes)
        if max_bytes <= 0:
            raise arg_value_error_range("native_anim_max_bytes", max_bytes)

        __class__._native_anim_max_bytes = max_bytes

    @native_anim_max_bytes.deleter
    def native_anim_max_bytes(self):
        __class__._native_anim_max_bytes = __class__.__native_anim_max_bytes

    read_from_file = ClassInstanceProperty(
        lambda self: getattr(self, "_read_from_file", True),
        doc="""Read-from-file optimization

        See the base instance of this metaclass for the complete description.
        """,
    )

    @read_from_file.setter
    def read_from_file(self, policy: bool) -> None:
        if not isinstance(policy, bool):
            raise arg_type_error("read_from_file", policy)

        self._read_from_file = policy

    @read_from_file.deleter
    def read_from_file(self) -> None:
        try:
            del self._read_from_file
        except AttributeError:
            pass


class ITerm2Image(GraphicsImage, metaclass=ITerm2ImageMeta):
    """A render style using the iTerm2 inline image protocol.

    See :py:class:`GraphicsImage` for the complete description of the constructor.

    |

    **Render Methods**

    :py:class:`ITerm2Image` provides two methods of :term:`rendering` images, namely:

    LINES (default)
       Renders an image line-by-line i.e the image is evenly split across the number
       of lines it should occupy.

       Pros:

       * Good for use cases where it might be required to trim some lines of the image.

       Cons:

       * Image drawing is significantly slower on iTerm2 due to the terminal emulator's
         performance.

    WHOLE
       Renders an image all at once i.e the entire image data is encoded into one
       line of the :term:`render` output, such that the entire image is drawn once
       by the terminal and still occupies the correct amount of lines and columns.

       Pros:

       * Render results are more compact (i.e less in character count) than with
         the **LINES** method since the entire image is encoded at once.
       * Image drawing is faster than with **LINES** on most terminals.
       * Smoother animations.

       Cons:

       * This method currently doesn't work well on iTerm2 and WezTerm when the image
         height is greater than the terminal height.

    ANIM
        Renders an animated image to utilize the protocol's native animation feature
        [1]_.

        Similar to the **WHOLE** render method, except that the terminal emulator
        animates the image, provided it supports the feature of the protocol.
        The animation is completely controlled by the terminal emulator.

        .. note::
            * If the image data size (in bytes) is greater than the value of
              :py:attr:`native_anim_max_bytes`, a warning is issued.
            * If used with :py:class:`~term_image.image.ImageIterator` or an animation,
              the **WHOLE** render method is used instead.
            * If the image is non-animated, the **WHOLE** render method is used instead.

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

      * ``None`` → the current effective render method of the instance is used
      * A valid render method name (as specified in the **Render Methods** section
        above) → used instead of the current effective render method of the instance
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

    |

    **Format Specification**

    See :ref:`format-spec`.

    ::

        [ <method> ]  [ m <mix> ]  [ c <compress> ]

    * ``method`` → render method override

      * ``L`` → **LINES** render method (current frame only, for animated images)
      * ``W`` → **WHOLE** render method (current frame only, for animated images)
      * ``A`` → **ANIM** render method [1]_
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
        map(re.compile, "[LWA] m[01] c[0-9]".split(" "))
    )
    _render_methods: Set[str] = {LINES, WHOLE, ANIM}
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
    }

    _TERM: str = ""
    _TERM_VERSION: str = ""

    jpeg_quality = ClassInstanceProperty(
        ITerm2ImageMeta.jpeg_quality.fget,
        ITerm2ImageMeta.jpeg_quality.fset,
        ITerm2ImageMeta.jpeg_quality.fdel,
        doc="""JPEG encoding quality

        :type: int

        GET:
            Returns the effective JPEG encoding quality of the invoker
            (class or instance).

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
        * an **instance**, it uses that of its class.

        By **default**, the quality is **unset** (i.e JPEG encoding is **disabled**) and
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

    native_anim_max_bytes = ClassProperty(
        lambda self: type(self)._native_anim_max_bytes,
        doc="""Maximum size (in bytes) of image data for native animation

        :type: int

        GET:
            Returns the set value.

        SET:
            A positive integer; the value is set.

            Can not be set via an instance.

        DELETE:
            The value is reset to the default.

            Can not be reset via an instance.

        :py:class:`~term_image.exceptions.TermImageWarning` is issued (and shown
        **only the first time**, except the warning filters are modified to do
        otherwise) if the image data size for a native animation is above this value.

        NOTE:
            This property is a global setting. Hence, setting/resetting it on this
            class or any subclass affects all classes and their instances.

        WARNING:
            This property should be altered with caution to avoid excessive memory
            usage, particularly on the terminal emulator's end.
        """,
    )

    read_from_file = ClassInstanceProperty(
        ITerm2ImageMeta.read_from_file.fget,
        ITerm2ImageMeta.read_from_file.fset,
        ITerm2ImageMeta.read_from_file.fdel,
        doc="""Read-from-file optimization

        :type: bool

        GET:
            Returns the effective read-from-file policy of the invoker
            (class or instance).

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
        * an **instance**, it uses that of its class.

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
        if not isinstance(cursor, bool):
            raise arg_type_error("cursor", cursor)
        if not isinstance(now, bool):
            raise arg_type_error("now", now)

        # There's no point checking for forced support since this is only required on
        # konsole which supports the protocol.
        # `is_supported()` is first called to ensure `_TERM` has been set.
        if cls.is_supported() and cls._TERM == "konsole":
            # Konsole utilizes the same image rendering implementation as it
            # uses for the kiity graphics protocol.
            (write_tty if now else _stdout_write)(
                (ctlseqs.KITTY_DELETE_CURSOR_b if now else ctlseqs.KITTY_DELETE_CURSOR)
                if cursor
                else (ctlseqs.KITTY_DELETE_ALL_b if now else ctlseqs.KITTY_DELETE_ALL)
            )

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
        if method:
            args["method"] = {"L": LINES, "W": WHOLE, "A": ANIM}[method]
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
        **kwargs,
    ):
        if not mix and self._TERM == "wezterm":
            lines = max(fmt[-1], self.rendered_height)
            r_width = self.rendered_width
            erase_and_move_cursor = ERASE_CHARS % r_width + CURSOR_FORWARD % r_width
            first_frame = self._format_render(
                f"{erase_and_move_cursor}\n" * (lines - 1) + erase_and_move_cursor,
                *fmt,
            )
            print(
                first_frame,
                "\r",
                CURSOR_UP % (lines - 1),
                sep="",
                end="",
                flush=True,
            )

        super()._display_animated(img, alpha, fmt, *args, mix=True, **kwargs)

    @staticmethod
    def _handle_interrupted_draw():
        """Performs necessary actions when image drawing is interrupted.

        If drawing is interrupted while transmitting an image, it causes terminal to
        wait for more data (while consuming any output following) until the output
        reaches the expected payload size or ST (String Terminator) is written.
        """

        # End last transmission (does no harm if there wasn't an unterminated
        # transmission)
        # Konsole sometimes requires ST to be written twice.
        print(ctlseqs.ST * 2, end="", flush=True)

    def _render_image(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        frame: bool = False,
        method: Optional[str] = None,
        mix: bool = False,
        compress: int = 4,
    ) -> str:
        # NOTE: It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        # Using `width=<columns>`, `height=<lines>` and `preserveAspectRatio=0` ensures
        # that an image always occupies the correct amount of columns and lines even if
        # the cell size has changed when it's drawn.
        # Since we use `width` and `height` control data keys, there's no need
        # upscaling the image on this end to reduce payload.
        # Anyways, this also implies that the image(s) have to be resized by the
        # terminal emulator, thereby leaving various details of resizing in the hands
        # of the terminal emulator such as the resampling method, etc.
        # This particularly affects the LINES render method negatively, resulting in
        # slant/curved edges not lining up across lines (amongst other artifacts
        # observed on Konsole) supposedly because the terminal emulator resizes each
        # line separately.
        # Hence, this optimization is only used for the WHOLE render method.

        r_width, r_height = self.rendered_size
        render_method = (method or self._render_method).lower()

        # Workarounds
        is_on_konsole = self._TERM == "konsole"
        is_on_wezterm = self._TERM == "wezterm"
        cursor_right = CURSOR_FORWARD % r_width
        cursor_up = CURSOR_UP % (r_height - 1) if r_height > 1 else ""
        erase = ERASE_CHARS % r_width if not mix and is_on_wezterm else ""

        file_is_readable = True
        if self._source_type is ImageSource.PIL_IMAGE:
            try:
                file_is_readable = os.access(img.filename, os.R_OK)
            except (AttributeError, OSError):
                file_is_readable = False

        if render_method == ANIM and self._is_animated and not frame:
            if self._source_type is ImageSource.PIL_IMAGE:
                if file_is_readable:
                    compressed_image = open(img.filename, "rb")
                else:
                    compressed_image = io.BytesIO()
                    try:
                        img.save(compressed_image, img.format, save_all=True)
                    except ValueError as e:
                        self._close_image(img)
                        raise RenderError(
                            "iTerm2 native animation not supported: This image was "
                            "sourced from a PIL image with an unknown format"
                        ) from e
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
                            else f"{erase}{cursor_right}\n" * (r_height - 1)
                        ),
                        erase,
                        "" if is_on_konsole else cursor_up,
                        ITERM2_START,
                        control_data,
                        standard_b64encode(compressed_image.read()).decode(),
                        ST,
                        f"{cursor_right}\n" * (r_height - 1) if is_on_konsole else "",
                        cursor_right * is_on_konsole,
                    )
                )

        width, height = (
            self._get_minimal_render_size()
            if render_method == WHOLE
            else self._get_render_size()
        )

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
                    buffer.write(ITERM2_START)
                    buffer.write(f"size={compressed_image.tell()}")
                    buffer.write(control_data)
                    buffer.write(
                        standard_b64encode(compressed_image.getvalue()).decode()
                    )
                    buffer.write(ST)
                    is_on_konsole and buffer.write(cursor_right)
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
                    (
                        ""
                        if is_on_konsole
                        else f"{erase}{cursor_right}\n" * (r_height - 1)
                    ),
                    erase,
                    "" if is_on_konsole else cursor_up,
                    ITERM2_START,
                    control_data,
                    standard_b64encode(compressed_image.read()).decode(),
                    ST,
                    f"{cursor_right}\n" * (r_height - 1) if is_on_konsole else "",
                    cursor_right * is_on_konsole,
                )
            )


_stdout_write = sys.stdout.write
