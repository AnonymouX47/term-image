"""
.. Core Library Definitions
"""

from __future__ import annotations

__all__ = ("TermImage", "ImageIterator")

import io
import os
import re
import time
from math import ceil
from operator import gt, mul, sub
from random import randint
from shutil import get_terminal_size
from types import FunctionType, TracebackType
from typing import Any, Optional, Tuple, Union
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError

from .exceptions import InvalidSize, TermImageException, URLNotFoundError

_ALPHA_THRESHOLD = 40 / 255  # Default alpha threshold
_FG_FMT = "\033[38;2;%d;%d;%dm"
_BG_FMT = "\033[48;2;%d;%d;%dm"
_RESET = "\033[0m"
_UPPER_PIXEL = "\u2580"  # upper-half block element
_LOWER_PIXEL = "\u2584"  # lower-half block element
_FORMAT_SPEC = re.compile(
    r"(([<|>])?(\d+)?)?(\.([-^_])?(\d+)?)?(#(\.\d+|[0-9a-f]{6})?)?",
    re.ASCII,
)
_NO_VERTICAL_SPEC = re.compile(r"(([<|>])?(\d+)?)?\.(#(\.\d+|[0-9a-f]{6})?)?", re.ASCII)
_HEX_COLOR_FORMAT = re.compile("#[0-9a-f]{6}", re.ASCII)


class TermImage:
    """Text-printable image

    Args:
        image: Source image.
        width: Horizontal dimension of the image, in columns.
        height: Vertical dimension of the image, in lines.
        scale: The fraction of the size on respective axes, to render the image with.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument has an unexpected/invalid value.

    Propagates exceptions raised by :py:meth:`set_size`, if *width* or *height* is
    given.

    NOTE:
        * *width* or *height* is the exact number of columns or lines that'll be used
          to draw the image (assuming the scale equal `1`), regardless of the currently
          set :term:`font ratio`.
        * If neither is given or both are ``None``, the size is automatically determined
          when the image is to be :term:`rendered`, such that it optimally fits
          into the terminal.
        * The image size is multiplied by the :term:`scale` on respective axes before
          the image is :term:`rendered`.
    """

    # Special Methods

    def __init__(
        self,
        image: Image.Image,
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        scale: Tuple[float, float] = (1.0, 1.0),
    ) -> None:
        """See class description"""
        if not isinstance(image, Image.Image):
            raise TypeError(
                "Expected a 'PIL.Image.Image' instance for 'image' "
                f"(got: {type(image).__name__!r})."
            )

        self._closed = False
        self._source = image
        self._original_size = image.size
        if width is None is height:
            self._size = None
        else:
            self.set_size(width, height)
        self._scale = []
        self._scale[:] = self._check_scale(scale)

        self._is_animated = hasattr(image, "is_animated") and image.is_animated
        if self._is_animated:
            self._frame_duration = (image.info.get("duration") or 100) / 1000
            self._seek_position = 0
            self._n_frames = None

        # Recognized sizing parameters.
        # These are initialized here only to avoid `AttributeError`s in case `_size` is
        # initially set via a means other than `set_size()`.
        self._fit_to_width = False
        self._h_allow = 0
        self._v_allow = 2  # A 2-line allowance for the shell prompt, etc

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> TermImage:
        return self

    def __exit__(self, typ: type, val: Exception, tb: TracebackType) -> bool:
        self.close()
        return False  # Currently, no particular exception is suppressed

    def __format__(self, spec: str) -> str:
        """Renders the image with alignment, padding and transparency control"""
        # Only the currently set frame is rendered for animated images
        h_align, width, v_align, height, alpha = self._check_format_spec(spec)

        return self._renderer(
            lambda image: self._format_render(
                self._render_image(image, alpha),
                h_align,
                width,
                v_align,
                height,
            )
        )

    def __iter__(self) -> ImageIterator:
        return ImageIterator(self, 1, "1.1", False)

    def __repr__(self) -> str:
        return (
            "<{}(source={!r}, original_size={}, size={}, scale={}, is_animated={})>"
        ).format(
            type(self).__name__,
            (self._url if hasattr(self, "_url") else self._source),
            self._original_size,
            self._size,
            self.scale,  # Stored as a list but should be shown as a tuple
            self._is_animated,
        )

    def __str__(self) -> str:
        """Renders the image with transparency enabled and without alignment"""
        # Only the currently set frame is rendered for animated images
        return self._renderer(lambda image: self._render_image(image, _ALPHA_THRESHOLD))

    # Properties

    closed = property(
        lambda self: self._closed,
        doc="Instance finalization status",
    )

    frame_duration = property(
        lambda self: self._frame_duration if self._is_animated else None,
        doc="""Duration (in seconds) of a single frame for :term:`animated` images

        Setting this on non-animated images is simply ignored, no exception is raised.
        """,
    )

    @frame_duration.setter
    def frame_duration(self, value: float) -> None:
        if not isinstance(value, float):
            raise TypeError(f"Invalid duration type (got: {type(value).__name__})")
        if value <= 0.0:
            raise ValueError(f"Invalid frame duration (got: {value})")
        if self._is_animated:
            self._frame_duration = value

    height = property(
        lambda self: self._size and self._size[1],
        lambda self, height: self.set_size(height=height),
        doc="""
        The **unscaled** height of the image.

        ``None`` when the image size is :ref:`unset <unset-size>`.

        Settable values:

            * ``None``: Sets the image size to an automatically calculated one,
              based on the current terminal size.
            * A positive ``int``: Sets the image height to the given value and
              the width proportionally.
        """,
    )

    is_animated = property(
        lambda self: self._is_animated,
        doc="``True`` if the image is :term:`animated`. Otherwise, ``False``.",
    )

    original_size = property(
        lambda self: self._original_size, doc="Size of the source image (in pixels)"
    )

    @property
    def n_frames(self) -> int:
        """The number of frames in the image"""
        if not self._is_animated:
            return 1

        if not self._n_frames:
            self._n_frames = (
                Image.open(self._source)
                if isinstance(self._source, str)
                else self._source
            ).n_frames

        return self._n_frames

    rendered_height = property(
        lambda self: round(
            (self._size or self._valid_size(None, None))[1] * self._scale[1]
        ),
        doc="""
        The **scaled** height of the image.

        Also the exact number of lines that the drawn image will occupy in a terminal.
        """,
    )

    rendered_size = property(
        lambda self: tuple(
            map(
                round,
                map(mul, self._size or self._valid_size(None, None), self._scale),
            )
        ),
        doc="""
        The **scaled** size of the image.

        Also the exact number of columns and lines (respectively) that the drawn image
        will occupy in a terminal.
        """,
    )

    rendered_width = property(
        lambda self: round(
            (self._size or self._valid_size(None, None))[0] * self._scale[0]
        ),
        doc="""
        The **scaled** width of the image.

        Also the exact number of columns that the drawn image will occupy in a terminal.
        """,
    )

    scale = property(
        lambda self: tuple(self._scale),
        doc="""
        Image :term:`scale`

        Settable values are:

            * A *scale value*; sets both axes.
            * A ``tuple`` of two *scale values*; sets ``(x, y)`` respectively.

        A scale value is a ``float`` in the range **0.0 < value <= 1.0**.
        """,
    )

    @scale.setter
    def scale(self, scale: Union[float, Tuple[float, float]]) -> None:
        if isinstance(scale, float):
            if not 0.0 < scale <= 1.0:
                raise ValueError(f"Scale value out of range (got: {scale})")
            self._scale[:] = (scale,) * 2
        elif isinstance(scale, tuple):
            self._scale[:] = self._check_scale(scale)
        else:
            raise TypeError("Given value must be a float or a tuple of floats")

    scale_x = property(
        lambda self: self._scale[0],
        doc="""
        Horizontal :term:`scale`

        A scale value is a ``float`` in the range **0.0 < x <= 1.0**.
        """,
    )

    @scale_x.setter
    def scale_x(self, x: float) -> None:
        self._scale[0] = self._check_scale_2(x)

    scale_y = property(
        lambda self: self._scale[1],
        doc="""
        Vertical :term:`scale`

        A scale value is a ``float`` in the range **0.0 < y <= 1.0**.
        """,
    )

    @scale_y.setter
    def scale_y(self, y: float) -> None:
        self._scale[1] = self._check_scale_2(y)

    size = property(
        lambda self: self._size,
        doc="""
        The **unscaled** size of the image.

        ``None`` when the image size is :ref:`unset <unset-size>`.

        Setting this to ``None`` :ref:`unsets <unset-size>` the image size (so that
        it's automatically calculated whenever the image is :term:`rendered`) and
        resets the recognized advanced sizing options to their defaults.

        This is multiplied by the :term:`scale` on respective axes before the image
        is :term:`rendered`.
        """,
    )

    @size.setter
    def size(self, value: None) -> None:
        if value is not None:
            raise TypeError("The only acceptable value is `None`")
        self._size = value
        self._fit_to_width = False
        self._h_allow = 0
        self._v_allow = 2  # A 2-line allowance for the shell prompt, etc

    source = property(
        lambda self: (self._url if hasattr(self, "_url") else self._source),
        doc="""
        The :term:`source` from which the instance was initialized

        Can be a PIL image, file path or URL.
        """,
    )

    width = property(
        lambda self: self._size and self._size[0],
        lambda self, width: self.set_size(width),
        doc="""
        The **unscaled** width of the image.

        ``None`` when the image size is :ref:`unset <unset-size>`.

        Settable values:

            * ``None``: Sets the image size to an automatically calculated one,
              based on the current terminal size.
            * A positive ``int``: Sets the image width to the given value and
              the height proportionally.
        """,
    )

    # Public Methods

    def close(self) -> None:
        """Finalizes the instance and releases external resources.

        * In most cases, it's not neccesary to explicity call this method, as it's
          automatically called when the instance is garbage-collected.
        * This method can be safely called mutiple times.
        * If the instance was initialized with a PIL image, the PIL image is never
          finalized.
        """
        try:
            if not self._closed:
                if (
                    hasattr(self, "_url")
                    # The file might not exist for whatever reason.
                    and os.path.exists(self._source)
                ):
                    os.remove(self._source)
        except AttributeError:
            # Instance creation or initialization was unsuccessful
            pass
        finally:
            self._closed = True

    def draw(
        self,
        h_align: Optional[str] = None,
        pad_width: Optional[int] = None,
        v_align: Optional[str] = None,
        pad_height: Optional[int] = None,
        alpha: Optional[float] = _ALPHA_THRESHOLD,
        *,
        scroll: bool = False,
        animate: bool = True,
        repeat: int = -1,
        cached: Union[bool, int] = 100,
        check_size: bool = True,
    ) -> None:
        """Draws/Displays an image in the terminal.

        Args:
            h_align: Horizontal alignment ("left" / "<", "center" / "|" or
              "right" / ">"). Default: center.
            pad_width: Number of columns within which to align the image.

              * Excess columns are filled with spaces.
              * Must not be greater than the
                :term:`available terminal width <available width>`.
              * Default: terminal width, minus horizontal allowance.

            v_align: Vertical alignment ("top"/"^", "middle"/"-" or "bottom"/"_").
              Default: middle.
            pad_height: Number of lines within which to align the image.

              * Excess lines are filled with spaces.
              * Must not be greater than the :term:`available terminal height
                <available height>`, **for animations**.
              * Default: terminal height, minus vertical allowance.

            alpha: Transparency setting.

              * If ``None``, transparency is disabled
                (uses the image's default background color).
              * If a ``float`` (**0.0 <= x < 1.0**), specifies the alpha ratio
                **above** which pixels are taken as *opaque*.
              * If a string, specifies a **hex color** with which transparent
                background should be replaced.

            scroll: Only applies to non-animations. If ``True``:

              * and the image size is set, allows the image's
                :term:`rendered height` to be greater than the
                :term:`available terminal height <available height>`.
              * and the image size is :ref:`unset <unset-size>`, the image is
                drawn to fit the terminal width.

            animate: If ``False``, disable animation i.e draw only the current frame of
              an animated image.
            repeat: The number of times to go over all frames of an animated image.
              A negative value implies infinite repetition.
            cached: Determines if :term:`rendered` frames of an animated image will be
              cached (for speed up of subsequent renders of the same frame) or not.

                - If ``bool``, it directly sets if the frames will be cached or not.
                - If ``int``, caching is enabled only if the framecount of the image
                  is less than or equal to the given number.

            check_size: If ``False``, does not perform size validation for
              non-animations.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
            ValueError: Image size or :term:`scale` too small.
            term_image.exceptions.InvalidSize: The image's :term:`rendered size` can not
              fit into the :term:`available terminal size <available size>`.

        * If :py:meth:`set_size` was directly used to set the image size, the values
          of the *fit_to_width*, *h_allow* and *v_allow* arguments
          (when :py:meth:`set_size` was called) are taken into consideration during
          size validation, with *fit_to_width* applying to only non-animations.
        * If the size was set via another means or the size is
          :ref:`unset <unset-size>`, the default values of those parameters are used.
        * If the image size was set with the *fit_to_width* parameter of
          :py:meth:`set_size` set to ``True``, then setting *scroll* is unnecessary.
        * *animate*, *repeat* and *cached* apply to :term:`animated` images only.
          They are simply ignored for non-animated images.
        * For animations (i.e animated images with *animate* set to ``True``):

          * *scroll* is ignored.
          * Image size and :term:`padding height` are always validated, if set or given.
        * Animations, **by default**, are infinitely looped and can be terminated
          with ``Ctrl-C`` (``SIGINT``), raising ``KeyboardInterrupt``.
        """
        fmt = self._check_formatting(h_align, pad_width, v_align, pad_height)

        if alpha is not None:
            if isinstance(alpha, float):
                if not 0.0 <= alpha < 1.0:
                    raise ValueError(f"Alpha threshold out of range (got: {alpha})")
            elif isinstance(alpha, str):
                if not _HEX_COLOR_FORMAT.fullmatch(alpha):
                    raise ValueError(f"Invalid hex color string (got: {alpha})")
            else:
                raise TypeError(
                    "'alpha' must be `None` or of type `float` or `str` "
                    f"(got: {type(alpha).__name__})"
                )

        if self._is_animated and not isinstance(animate, bool):
            raise TypeError("'animate' must be a boolean")

        if None is not pad_width > get_terminal_size()[0] - self._h_allow:
            raise ValueError(
                "Padding width is greater than the available terminal width"
            )

        if (
            self._is_animated
            and animate
            and None is not pad_height > get_terminal_size()[1]
        ):
            raise ValueError(
                "Padding height can not be greater than the terminal height for "
                "animations"
            )

        for arg in ("scroll", "check_size"):
            if not isinstance(locals()[arg], bool):
                raise TypeError(f"{arg!r} must be a boolean")

        # Checks for *repeat* and *cached* are delegated to `ImageIterator`.

        def render(image: Image.Image) -> None:
            print("\033[?25l", end="")  # Hide the cursor
            try:
                if self._is_animated and animate:
                    self._display_animated(image, alpha, fmt, repeat, cached)
                else:
                    print(
                        self._format_render(self._render_image(image, alpha), *fmt),
                        end="",
                        flush=True,
                    )
            finally:
                print("\033[0m\033[?25h")  # Reset color and show the cursor

        self._renderer(
            render,
            scroll=scroll,
            check_size=check_size,
            animated=self._is_animated and animate,
        )

    @classmethod
    def from_file(
        cls,
        filepath: str,
        **kwargs: Union[None, int, Tuple[float, float]],
    ) -> TermImage:
        """Creates a :py:class:`TermImage` instance from an image file.

        Args:
            filepath: Relative/Absolute path to an image file.
            kwargs: Same keyword arguments as the class constructor.

        Returns:
            A new :py:class:`TermImage` instance.

        Raises:
            TypeError: *filepath* is not a string.
            FileNotFoundError: The given path does not exist.
            IsADirectoryError: Propagated from from ``PIL.Image.open()``.
            UnidentifiedImageError: Propagated from from ``PIL.Image.open()``.

        Also Propagates exceptions raised or propagated by the class constructor.
        """
        if not isinstance(filepath, str):
            raise TypeError(
                f"File path must be a string (got: {type(filepath).__name__!r})."
            )

        # Intentionally propagates `IsADirectoryError` since the message is OK
        try:
            new = cls(Image.open(filepath), **kwargs)
        except FileNotFoundError:
            raise FileNotFoundError(f"No such file: {filepath!r}") from None
        except UnidentifiedImageError as e:
            e.args = (f"Could not identify {filepath!r} as an image",)
            raise

        # Absolute paths work better with symlinks, as opposed to real paths:
        # less confusing, Filename is as expected, helps in path comparisons
        new._source = os.path.abspath(filepath)
        return new

    @classmethod
    def from_url(
        cls,
        url: str,
        **kwargs: Union[None, int, Tuple[float, float]],
    ) -> TermImage:
        """Creates a :py:class:`TermImage` instance from an image URL.

        Args:
            url: URL of an image file.
            kwargs: Same keyword arguments as the class constructor.

        Returns:
            A new :py:class:`TermImage` instance.

        Raises:
            TypeError: *url* is not a string.
            ValueError: The URL is invalid.
            term_image.exceptions.URLNotFoundError: The URL does not exist.
            PIL.UnidentifiedImageError: Propagated from ``PIL.Image.open()``.

        Also propagates connection-related exceptions from ``requests.get()``
        and exceptions raised or propagated by the class constructor.

        NOTE:
            This method creates a temporary image file, but only after a successful
            initialization.

            Proper clean-up is guaranteed except maybe in very rare cases.

            To ensure 100% guarantee of clean-up, use the object as a
            :ref:`context manager <context-manager>`.
        """
        if not isinstance(url, str):
            raise TypeError(f"URL must be a string (got: {type(url).__name__!r}).")
        if not all(urlparse(url)[:3]):
            raise ValueError(f"Invalid URL: {url!r}")

        # Propagates connection-related errors.
        response = requests.get(url, stream=True)
        if response.status_code == 404:
            raise URLNotFoundError(f"URL {url!r} does not exist.")

        try:
            new = cls(Image.open(io.BytesIO(response.content)), **kwargs)
        except UnidentifiedImageError as e:
            e.args = (f"The URL {url!r} doesn't link to an identifiable image",)
            raise

        # Ensure initialization is successful before writing to file

        basedir = os.path.join(os.path.expanduser("~"), ".term_image", "temp")
        if not os.path.isdir(basedir):
            os.makedirs(basedir)

        filepath = os.path.join(basedir, os.path.basename(url))
        while os.path.exists(filepath):
            filepath += str(randint(0, 9))
        with open(filepath, "wb") as image_writer:
            image_writer.write(response.content)

        new._source = filepath
        new._url = url
        return new

    def seek(self, pos: int) -> None:
        """Changes current image frame.

        Args:
            pos: New frame number.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument has an unexpected/invalid value but of an
              appropriate type.

        Frame numbers start from 0 (zero).
        """
        if not isinstance(pos, int):
            raise TypeError(f"Invalid frame number type (got: {type(pos).__name__})")
        if not 0 <= pos < self.n_frames:
            raise ValueError(
                f"Frame number out of range (got: {pos}, n_frames={self.n_frames})"
            )
        if self._is_animated:
            self._seek_position = pos

    def set_size(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        h_allow: int = 0,
        v_allow: int = 2,
        *,
        maxsize: Optional[Tuple[int, int]] = None,
        fit_to_width: bool = False,
        fit_to_height: bool = False,
    ) -> None:
        """Sets the image size with extended control.

        Args:
            width: Horizontal dimension of the image, in columns.
            height: Vertical dimension of the image, in lines.
            h_allow: Horizontal allowance i.e minimum number of columns to leave unused.
            v_allow: Vertical allowance i.e minimum number of lines to leave unused.
            maxsize: If given, as ``(columns, lines)``, it's used instead of the
              terminal size.
            fit_to_width: Only used with **automatic sizing**. See description below.
            fit_to_height: Only used with **automatic sizing**. See description below.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
            ValueError: Both *width* and *height* are specified.
            ValueError: *fit_to_width* or *fit_to_height* is ``True`` when *width*,
              *height* or *maxsize* is given.
            ValueError: The :term:`available size` is too small for automatic sizing.
            term_image.exceptions.InvalidSize: *maxsize* is given and the resulting
              size will not fit into it.

        If neither *width* nor *height* is given or anyone given is ``None``,
        **automatic sizing** applies. In such a case, if:

          * both *fit_to_width* and *fit_to_height* are ``False``, the size is
            set to fit **within** the :term:`available terminal size <available size>`
            (or *maxsize*, if given).
          * *fit_to_width* is ``True``, the size is set such that the
            :term:`rendered width` is exactly the
            :term:`available terminal width <available width>`
            (assuming the horizontal :term:`scale` equals 1),
            regardless of the :term:`font ratio`.
          * *fit_to_height* is ``True``, the size is set such that the
            :term:`rendered height` is exactly the
            :term:`available terminal height <available height>`
            (assuming the vertical :term:`scale` equals 1),
            regardless of the :term:`font ratio`.

        .. important::
            1. *fit_to_width* and *fit_to_height* are mutually exclusive.
               Only one can be ``True`` at a time.
            2. Neither *fit_to_width* nor *fit_to_height* may be ``True`` when *width*,
               *height* or *maxsize* is given.
            3. Be careful when setting *fit_to_height* to ``True`` as it might result
               in the image's :term:`rendered width` being larger than the terminal
               width (or maxsize[0]) because :py:meth:`draw` will (by default) raise
               :py:exc:`term_image.exceptions.InvalidSize` if such is the case.

        | :term:`Vertical allowance` does not apply when *fit_to_width* is ``True``.
        | :term:`horizontal allowance` does not apply when *fit_to_height* is ``True``.

        :term:`Allowance`\\ s are ignored when *maxsize* is given.

        *fit_to_width* might be set to ``True`` to set the image size for
        vertically-oriented images (i.e images with height > width) such that the
        drawn image spans more columns but the terminal window has to be scrolled
        to view the entire image.

        Image formatting and all size validation recognize and respect the values of
        the *fit_to_width*, *h_allow* and *v_allow* parameters,
        until the size is re-set or :ref:`unset <unset-size>`.

        *fit_to_height* is only provided for completeness, it should probably be used
        only when the image will not be drawn to the current terminal.
        The value of this parameter is **not** recognized by any other method or
        operation.

        .. note::
           The size is checked to fit in only when *maxsize* is given along with
           *width* or *height* because :py:meth:`draw` is generally not the means of
           drawing such an image and all rendering methods don't perform any sort of
           size validation.

           If the validation is not desired, specify only one of *maxsize* and
           *width* or *height*, not both.
        """
        if width is not None is not height:
            raise ValueError("Cannot specify both width and height")
        for argname, x in zip(("width", "height"), (width, height)):
            if not (x is None or isinstance(x, int)):
                raise TypeError(
                    f"{argname!r} must be `None` or an integer "
                    f"(got: type {type(x).__name__!r})"
                )
            if None is not x <= 0:
                raise ValueError(f"{argname!r} must be positive (got: {x})")

        for argname, x in zip(("h_allow", "v_allow"), (h_allow, v_allow)):
            if not isinstance(x, int):
                raise TypeError(
                    f"{argname!r} must be an integer (got: type {type(x).__name__!r})"
                )
            if x < 0:
                raise ValueError(f"{argname!r} must be non-negative (got: {x})")

        if maxsize is not None:
            if not (
                isinstance(maxsize, tuple) and all(isinstance(x, int) for x in maxsize)
            ):
                raise TypeError(
                    f"'maxsize' must be a tuple of integers (got: {maxsize!r})"
                )

            if not (len(maxsize) == 2 and all(x > 0 for x in maxsize)):
                raise ValueError(
                    f"'maxsize' must contain two positive integers (got: {maxsize})"
                )

        for arg in ("fit_to_width", "fit_to_height"):
            if not isinstance(locals()[arg], bool):
                raise TypeError(f"{arg!r} must be a boolean")
        if fit_to_width and fit_to_height:
            raise ValueError(
                "'fit_to_width' and 'fit_to_height` are mutually exclusive, only one "
                "can be `True`."
            )
        arg = "fit_to_width" if fit_to_width else "fit_to_height"
        if locals()[arg]:  # Both may be `False`
            for arg2 in ("width", "height", "maxsize"):
                if locals()[arg2]:
                    raise ValueError(f"{arg!r} cannot be `True` when {arg2!r} is given")

        self._size = self._valid_size(
            width,
            height,
            h_allow * (not fit_to_height),
            v_allow * (not fit_to_width),
            maxsize=maxsize,
            fit_to_width=fit_to_width,
            fit_to_height=fit_to_height,
        )
        self._fit_to_width = fit_to_width
        self._h_allow = h_allow * (not maxsize) * (not fit_to_height)
        self._v_allow = v_allow * (not maxsize) * (not fit_to_width)

    def tell(self) -> int:
        """Returns the current image frame number."""
        return self._seek_position if self._is_animated else 0

    # Private Methods

    def _check_format_spec(self, spec: str):
        """Validates a format specification and translates it into the required values.

        Returns:
            A tuple ``(h_align, width, v_align, height, alpha)`` containing values
            as required by ``_format_render()`` and ``_render_image()``.
        """
        match_ = _FORMAT_SPEC.fullmatch(spec)
        if not match_ or _NO_VERTICAL_SPEC.fullmatch(spec):
            raise ValueError(f"Invalid format specification (got: {spec!r})")

        _, h_align, width, _, v_align, height, alpha, threshold_or_bg = match_.groups()

        return (
            *self._check_formatting(
                h_align, width and int(width), v_align, height and int(height)
            ),
            (
                threshold_or_bg
                and (
                    "#" + threshold_or_bg
                    if _HEX_COLOR_FORMAT.fullmatch("#" + threshold_or_bg)
                    else float(threshold_or_bg)
                )
                if alpha
                else _ALPHA_THRESHOLD
            ),
        )

    def _check_formatting(
        self,
        h_align: Optional[str] = None,
        width: Optional[int] = None,
        v_align: Optional[str] = None,
        height: Optional[int] = None,
    ) -> Tuple[Union[None, str, int]]:
        """Validates formatting arguments while also translating literal ones.

        Returns:
            The respective arguments appropriate for ``_format_render()``.
        """
        if not isinstance(h_align, (type(None), str)):
            raise TypeError("'h_align' must be a string.")
        if None is not h_align not in set("<|>"):
            align = {"left": "<", "center": "|", "right": ">"}.get(h_align)
            if not align:
                raise ValueError(f"Invalid horizontal alignment option: {h_align!r}")
            h_align = align

        if not isinstance(width, (type(None), int)):
            raise TypeError("Padding width must be `None` or an integer.")
        if width is not None:
            if width <= 0:
                raise ValueError(f"Padding width must be positive (got: {width})")

        if not isinstance(v_align, (type(None), str)):
            raise TypeError("'v_align' must be a string.")
        if None is not v_align not in set("^-_"):
            align = {"top": "^", "middle": "-", "bottom": "_"}.get(v_align)
            if not align:
                raise ValueError(f"Invalid vertical alignment option: {v_align!r}")
            v_align = align

        if not isinstance(height, (type(None), int)):
            raise TypeError("Padding height must be `None` or an integer.")
        if None is not height <= 0:
            raise ValueError(f"Padding height must be positive (got: {height})")

        return h_align, width, v_align, height

    @staticmethod
    def _check_scale(scale: Tuple[float, float]) -> Tuple[float, float]:
        """Checks a tuple of scale values.

        Returns:
            The tuple of scale values, if valid.

        Raises:
            TypeError: The object is not a tuple of ``float``\\ s.
            ValueError: The object is not a 2-tuple or the values are out of range.
        """
        if not (isinstance(scale, tuple) and all(isinstance(x, float) for x in scale)):
            raise TypeError(f"'scale' must be a tuple of floats (got: {scale!r})")

        if not (len(scale) == 2 and all(0.0 < x <= 1.0 for x in scale)):
            raise ValueError(
                f"'scale' must be a tuple of two floats, 0.0 < x <= 1.0 (got: {scale})"
            )
        return scale

    @staticmethod
    def _check_scale_2(value: float) -> float:
        """Checks a single scale value.

        Returns:
            The scale value, if valid.

        Raises:
            TypeError: The object is not a ``float``.
            ValueError: The value is out of range.
        """
        if not isinstance(value, float):
            raise TypeError(
                f"Given value must be a float (got: type {type(value).__name__!r})"
            )
        if not 0.0 < value <= 1.0:
            raise ValueError(f"Scale value out of range (got: {value})")
        return value

    def _display_animated(
        self,
        img: Image.Image,
        alpha: Union[None, float, str],
        fmt: Tuple[Union[None, str, int]],
        repeat: int,
        cached: Union[bool, int],
    ) -> None:
        """Displays an animated GIF image in the terminal.

        NOTE: This is done indefinitely but can be terminated with ``Ctrl-C``
          (``SIGINT``), raising ``KeyboardInterrupt``.
        """
        lines = max(
            (fmt or (None,))[-1] or get_terminal_size()[1] - self._v_allow,
            self.rendered_height,
        )
        prev_seek_pos = self._seek_position
        image_it = ImageIterator(self, repeat, "", cached)
        del image_it._animator

        try:
            duration = self._frame_duration
            start = time.time()
            for frame in image_it._animate(img, alpha, fmt):
                print(frame, end="", flush=True)  # Current frame

                # Left-over of current frame's duration
                time.sleep(max(0, duration - (time.time() - start)))

                # Render next frame during current frame's duration
                start = time.time()

                # Move cursor up to the begining of the first line of the image
                # Not flushed until the next frame is printed
                print("\r\033[%dA" % (lines - 1), end="")
        finally:
            if img is not self._source:
                img.close()
            self._seek_position = prev_seek_pos
            # Move the cursor to the line after the image
            # Prevents "overlayed" output in the terminal
            print("\033[%dB" % lines, end="")

    def _format_render(
        self,
        render: str,
        h_align: Optional[str] = None,
        width: Optional[int] = None,
        v_align: Optional[str] = None,
        height: Optional[int] = None,
    ) -> str:
        """Formats rendered image text.

        All arguments should be passed through ``_check_formatting()`` first.
        """
        lines = render.splitlines()
        cols, rows = self.rendered_size

        width = width or get_terminal_size()[0] - self._h_allow
        width = max(cols, width)
        if h_align == "<":  # left
            pad_left = ""
            pad_right = " " * (width - cols)
        elif h_align == ">":  # right
            pad_left = " " * (width - cols)
            pad_right = ""
        else:  # center
            pad_left = " " * ((width - cols) // 2)
            pad_right = " " * (width - cols - len(pad_left))

        if pad_left and pad_right:
            lines = [pad_left + line + pad_right for line in lines]
        elif pad_left:
            lines = [pad_left + line for line in lines]
        elif pad_right:
            lines = [line + pad_right for line in lines]

        height = height or get_terminal_size()[1] - self._v_allow
        height = max(rows, height)
        if v_align == "^":  # top
            pad_up = 0
            pad_down = height - rows
        elif v_align == "_":  # bottom
            pad_up = height - rows
            pad_down = 0
        else:  # middle
            pad_up = (height - rows) // 2
            pad_down = height - rows - pad_up

        if pad_down:
            lines[rows:] = (" " * width,) * pad_down
        if pad_up:
            lines[:0] = (" " * width,) * pad_up

        return "\n".join(lines)

    def _get_render_size(self) -> Tuple[int, int]:
        """Returns the size (in pixels) required to render the image.

        Applies the image scale.
        """
        return tuple(map(mul, self.rendered_size, (1, 2)))

    @staticmethod
    def _pixels_cols(
        *, pixels: Optional[int] = None, cols: Optional[int] = None
    ) -> int:
        """Returns the number of pixels represented by a given number of columns
        or vice-versa.
        """
        return pixels if pixels is not None else cols

    @staticmethod
    def _pixels_lines(
        *, pixels: Optional[int] = None, lines: Optional[int] = None
    ) -> int:
        """Returns the number of pixels represented by a given number of lines
        or vice-versa.
        """
        return ceil(pixels / 2) if pixels is not None else lines * 2

    def _render_image(self, image: Image.Image, alpha: Union[None, float, str]) -> str:
        """Converts image pixel data into a "color-coded" string.

        Two pixels per character using FG and BG colors.

        NOTE: This method is not meant to be used directly, use it via `_renderer()`
        instead.
        """
        if self._closed:
            raise TermImageException("This image has been finalized")

        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        buffer = io.StringIO()
        # Eliminate attribute resolution cost
        buf_write = buffer.write

        def update_buffer():
            if alpha:
                no_alpha = False
                if a_cluster1 == 0 == a_cluster2:
                    buf_write(_RESET)
                    buf_write(" " * n)
                elif a_cluster1 == 0:  # up is transparent
                    buf_write(_RESET)
                    buf_write(_FG_FMT % cluster2)
                    buf_write(_LOWER_PIXEL * n)
                elif a_cluster2 == 0:  # down is transparent
                    buf_write(_RESET)
                    buf_write(_FG_FMT % cluster1)
                    buf_write(_UPPER_PIXEL * n)
                else:
                    no_alpha = True

            if not alpha or no_alpha:
                buf_write(_BG_FMT % cluster2)
                if cluster1 == cluster2:
                    buf_write(" " * n)
                else:
                    buf_write(_FG_FMT % cluster1)
                    buf_write(_UPPER_PIXEL * n)

        if self._is_animated:
            image.seek(self._seek_position)

        width, height = self._get_render_size()

        if alpha is None or image.mode == "RGB":
            try:
                image = image.convert("RGB").resize((width, height))
            except ValueError:
                raise ValueError("Image size or scale too small") from None
            rgb = tuple(image.getdata())
            a = (255,) * (width * height)
            alpha = None
        else:
            try:
                image = image.convert("RGBA").resize((width, height))
            except ValueError:
                raise ValueError("Image size or scale too small") from None
            if isinstance(alpha, str):
                bg = Image.new("RGBA", image.size, alpha)
                bg.alpha_composite(image)
                if image is not self._source:
                    image.close()
                image = bg
                alpha = None
            rgb = tuple(image.convert("RGB").getdata())
            if alpha is None:
                a = (255,) * (width * height)
            else:
                alpha = round(alpha * 255)
                a = [0 if val < alpha else val for val in image.getdata(3)]
                # To distinguish `0.0` from `None` in truth value tests
                if alpha == 0.0:
                    alpha = True

        # clean up
        if image is not self._source:
            image.close()

        rgb_pairs = (
            (
                zip(rgb[x : x + width], rgb[x + width : x + width * 2]),
                (rgb[x], rgb[x + width]),
            )
            for x in range(0, len(rgb), width * 2)
        )
        a_pairs = (
            (
                zip(a[x : x + width], a[x + width : x + width * 2]),
                (a[x], a[x + width]),
            )
            for x in range(0, len(a), width * 2)
        )

        row_no = 0
        # Two rows of pixels per line
        for (rgb_pair, (cluster1, cluster2)), (a_pair, (a_cluster1, a_cluster2)) in zip(
            rgb_pairs, a_pairs
        ):
            row_no += 2
            n = 0
            for (px1, px2), (a1, a2) in zip(rgb_pair, a_pair):
                # Color-code characters and write to buffer
                # when upper and/or lower pixel color/alpha-level changes
                if not (alpha and a1 == a_cluster1 == 0 == a_cluster2 == a2) and (
                    px1 != cluster1
                    or px2 != cluster2
                    or alpha
                    and (
                        # From non-transparent to transparent
                        a_cluster1 != a1 == 0
                        or a_cluster2 != a2 == 0
                        # From transparent to non-transparent
                        or 0 == a_cluster1 != a1
                        or 0 == a_cluster2 != a2
                    )
                ):
                    update_buffer()
                    cluster1 = px1
                    cluster2 = px2
                    if alpha:
                        a_cluster1 = a1
                        a_cluster2 = a2
                    n = 0
                n += 1
            # Rest of the line
            update_buffer()
            if row_no < height:  # last line not yet rendered
                buf_write("\033[0m\n")

        buf_write(_RESET)  # Reset color after last line
        buffer.seek(0)  # Reset buffer pointer

        return buffer.getvalue()

    def _renderer(
        self,
        renderer: FunctionType,
        *args: Any,
        scroll: bool = False,
        check_size: bool = False,
        animated: bool = False,
        **kwargs,
    ) -> Any:
        """Performs common render preparations and a rendering operation.

        Args:
            renderer: The function to perform the specifc rendering operation for the
              caller of this method, ``_renderer()``.
              This function must accept at least one positional argument, the
              ``PIL.Image.Image`` instance corresponding to the source.
            args: Positional arguments to pass on to *renderer*, after the
              ``PIL.Image.Image`` instance.
            scroll: See *scroll* in ``draw()``.
            check_size: See *check_size* in ``draw()``.
            animated: If ``True``, *scroll* and *check_size* are ignored and the size
              is validated.
            kwargs: Keyword arguments to pass on to *renderer*.

        Returns:
            The return value of *renderer*.

        Raises:
            term_image.exceptions.InvalidSize: *check_size* or *animated* is ``True``
              and the image's :term:`rendered size` can not fit into the
              :term:`available terminal size <available size>`.
            term_image.exceptions.TermImageException: The image has been finalized.

        NOTE:
            * If the ``set_size()`` method was previously used to set the image size,
              (directly or not), the last value of its *fit_to_width* parameter
              is taken into consideration, for non-animations.
        """
        if self._closed:
            raise TermImageException("This image has been finalized")

        try:
            reset_size = False
            if not self._size:  # Size is unset
                self.set_size(fit_to_width=scroll and not animated)
                reset_size = True

            # If the set size is larger than the available terminal size but the scale
            # makes it fit in, then it's all good.
            elif check_size or animated:
                columns, lines = map(
                    sub,
                    get_terminal_size(),
                    # *scroll* nullifies vertical allowance for non-animations
                    # Makes a difference when terminal height < vertical allowance
                    (self._h_allow, self._v_allow * (animated or not scroll)),
                )

                if any(
                    map(
                        gt,
                        # the compared height will be 0 if *_fit_to_width* or *scroll*
                        # is `True`. So, the height comparison will always be `False`
                        # since the terminal height should never be < 0.
                        map(
                            mul,
                            self.rendered_size,
                            (1, not (self._fit_to_width or scroll)),
                        ),
                        (columns, lines),
                    )
                ):
                    raise InvalidSize(
                        "The "
                        + ("animation" if animated else "image")
                        + " cannot fit into the available terminal size"
                    )

                # Reaching here means it's either valid or *_fit_to_width* and/or
                # *scroll* is/are `True`.
                if animated and self.rendered_height > lines:
                    raise InvalidSize(
                        "The rendered height cannot be greater than the terminal "
                        "height for animations"
                    )

            image = (
                Image.open(self._source)
                if isinstance(self._source, str)
                else self._source
            )

            return renderer(image, *args, **kwargs)

        finally:
            if reset_size:
                self._size = None

    def _valid_size(
        self,
        width: Optional[int],
        height: Optional[int],
        h_allow: int = 0,
        v_allow: int = 2,
        *,
        maxsize: Optional[Tuple[int, int]] = None,
        fit_to_width: bool = False,
        fit_to_height: bool = False,
    ) -> Tuple[int, int]:
        """Returns an image size tuple.

        See the description of ``set_size()`` for the parameters.
        """
        ori_width, ori_height = self._original_size
        columns, lines = maxsize or map(sub, get_terminal_size(), (h_allow, v_allow))
        max_width = self._pixels_cols(cols=columns)
        max_height = self._pixels_lines(lines=lines)

        # NOTE: The image scale is not considered since it should never be > 1

        # As for font ratio...
        #
        # Take for example, pixel ratio = 2.0
        # (i.e font ratio = 1.0; square character cells).
        # To adjust the image to the proper scale, we either reduce the
        # width (i.e divide by 2.0) or increase the height (i.e multiply by 2.0).
        #
        # On the other hand, if the pixel ratio = 0.5
        # (i.e font ratio = 0.25; vertically oblong character cells).
        # To adjust the image to the proper scale, we either increase the width
        # (i.e divide by the 0.5) or reduce the height (i.e multiply by the 0.5).
        #
        # Therefore, for the height, we always multiply by the pixel ratio
        # and for the width, we always divide by the pixel ratio.
        # The non-constraining axis is always the one directly adjusted.

        if width is None is height:
            for name in ("columns", "lines"):
                if locals()[name] <= 0:
                    raise ValueError(f"Amount of available {name} too small")

            if fit_to_width:
                return (
                    self._pixels_cols(pixels=max_width),
                    self._pixels_lines(
                        pixels=round(self._width_height_px(w=max_width) * _pixel_ratio)
                    ),
                )
            if fit_to_height:
                return (
                    self._pixels_cols(
                        pixels=round(self._width_height_px(h=max_height) / _pixel_ratio)
                    ),
                    self._pixels_lines(pixels=max_height),
                )

            # The smaller fraction will fit on both axis.
            # Hence, the axis with the smaller ratio is the constraining axis.
            # Constraining by the axis with the larger ratio will cause the image
            # to not fit into the axis with the smaller ratio.
            x = max_width / ori_width
            y = max_height / ori_height
            _width_px = ori_width * min(x, y)
            _height_px = ori_height * min(x, y)

            # The font ratio should affect the axis with the larger ratio since the axis
            # the smaller ratio is already fully occupied

            if x < y:
                _height_px = _height_px * _pixel_ratio
                # If height becomes greater than the max, reduce it to the max
                height_px = min(_height_px, max_height)
                # Calculate the corresponding width
                width_px = round((height_px / _height_px) * _width_px)
                # Round the height
                height_px = round(height_px)
            else:
                _width_px = _width_px / _pixel_ratio
                # If width becomes greater than the max, reduce it to the max
                width_px = min(_width_px, max_width)
                # Calculate the corresponding height
                height_px = round((width_px / _width_px) * _height_px)
                # Round the width
                width_px = round(width_px)
            return (
                self._pixels_cols(pixels=width_px),
                self._pixels_lines(pixels=height_px),
            )
        elif width is None:
            width_px = round(
                self._width_height_px(h=self._pixels_lines(lines=height)) / _pixel_ratio
            )
            width = self._pixels_cols(pixels=width_px)
        elif height is None:
            height_px = round(
                self._width_height_px(w=self._pixels_cols(cols=width)) * _pixel_ratio
            )
            height = self._pixels_lines(pixels=height_px)

        if maxsize and (width > columns or height > lines):
            raise InvalidSize(
                f"The resulting size {width, height} will not fit into "
                f"'maxsize' {maxsize}"
            )

        return (width, height)

    def _width_height_px(
        self, *, w: Optional[int] = None, h: Optional[int] = None
    ) -> float:
        """Converts the given width (in pixels) to the **unrounded** proportional height
        (in pixels) OR vice-versa.
        """
        ori_width, ori_height = self._original_size
        return (
            (w / ori_width) * ori_height
            if w is not None
            else (h / ori_height) * ori_width
        )


class ImageIterator:
    """Effeciently iterate over :term:`rendered` frames of an :term:`animated` image

    Args:
        image: Animated image.
        repeat: The number of times to go over the entire image. A negative value
          implies infinite repetition.
        format: The :ref:`format specification <format-spec>` to be used to format the
          rendered frames (default: auto).
        cached: Determines if the :term:`rendered` frames will be cached (for speed up
          of subsequent renders) or not.

          * If ``bool``, it directly sets if the frames will be cached or not.
          * If ``int``, caching is enabled only if the framecount of the image
            is less than or equal to the given number.

    * If *repeat* equals ``1``, caching is disabled.
    * The iterator has immediate response to changes in the image size
      and :term:`scale`.
    * If the image size is :ref:`unset <unset-size>`, it's automatically
      calculated per frame.
    * The current frame number reflects on the underlying image during iteration.
    * After the iterator is exhausted, the underlying image is set to frame `0`.
    """

    def __init__(
        self,
        image: TermImage,
        repeat: int = -1,
        format: str = "",
        cached: Union[bool, int] = 100,
    ) -> None:
        if not isinstance(image, TermImage):
            raise TypeError(f"Invalid type for 'image' (got: {type(image).__name__})")
        if not image._is_animated:
            raise ValueError("This image is not animated")

        if not isinstance(repeat, int):
            raise TypeError(f"Invalid type for 'repeat' (got: {type(repeat).__name__})")
        if not repeat:
            raise ValueError("'repeat' must be non-zero")

        if not isinstance(format, str):
            raise TypeError(
                "Invalid type for 'format' " f"(got: {type(format).__name__})"
            )
        *fmt, alpha = image._check_format_spec(format)

        if not isinstance(cached, int):  # `bool` is a subclass of `int`
            raise TypeError(f"Invalid type for 'cached' (got: {type(cached).__name__})")
        if False is not cached <= 0:
            raise ValueError("'cached' must be a boolean or a positive integer")

        self._image = image
        self._repeat = repeat
        self._format = format
        self._cached = (
            cached if isinstance(cached, bool) else image.n_frames <= cached
        ) and repeat != 1
        self._animator = image._renderer(self._animate, alpha, fmt, check_size=False)

    def __del__(self) -> None:
        self.close()

    def __iter__(self) -> None:
        return self

    def __next__(self) -> None:
        try:
            return next(self._animator)
        except StopIteration:
            self.close()
            raise StopIteration(
                "Iteration has reached the given repeat count"
            ) from None
        except AttributeError as e:
            if str(e).endswith("'_animator'"):
                raise StopIteration("Iterator exhausted or closed") from None
            else:
                self.close()
                raise
        except Exception:
            self.close()
            raise

    def __repr__(self) -> None:
        return "{}(image={!r}, repeat={}, format={!r}, cached={})".format(
            type(self).__name__,
            *self.__dict__.values(),
        )

    def close(self) -> None:
        """Closes the iterator and releases resources used.

        Does not reset the frame number of the underlying image.

        NOTE:
            This methods is automatically called when the iterator is exhausted or
            garbage-collected.
        """
        try:
            self._animator.close()
            del self._animator
            if self._img is not self._image._source:
                self._img.close()
            del self._img
        except AttributeError:
            pass

    def _animate(
        self,
        img: Image.Image,
        alpha: Union[None, float, str],
        fmt: Tuple[Union[None, str, int]],
    ) -> None:
        """Returns a generator that yields rendered and formatted frames of the
        underlying image.
        """
        self._img = img  # For cleanup
        image = self._image
        cached = self._cached
        repeat = self._repeat
        if cached:
            cache = []

        # Size must be set before hashing, since `None` will always
        # compare equal but doesn't mean the size is the same.
        unset_size = not image._size
        if unset_size:
            image.set_size()

        image._seek_position = 0
        frame = image._format_render(image._render_image(img, alpha), *fmt)
        while repeat:
            if cached:
                cache.append((frame, hash(image._size)))

            if unset_size:
                image._size = None

            yield frame
            image._seek_position += 1

            # Size must be set before hashing, since `None` will always
            # compare equal but doesn't mean the size is the same.
            unset_size = not image._size
            if unset_size:
                image.set_size()

            try:
                frame = image._format_render(image._render_image(img, alpha), *fmt)
            except EOFError:
                image._seek_position = 0
                if repeat > 0:  # Avoid infinitely large negative numbers
                    repeat -= 1
                if cached:
                    break
                if repeat:
                    frame = image._format_render(image._render_image(img, alpha), *fmt)

        if unset_size:
            image._size = None

        if cached:
            n_frames = len(cache)
        while repeat:
            n = 0
            while n < n_frames:
                # Size must be set before hashing, since `None` will always
                # compare equal but doesn't mean the size is the same.
                unset_size = not image._size
                if unset_size:
                    image.set_size()

                frame, size_hash = cache[n]
                if hash(image._size) != size_hash:
                    frame = image._format_render(image._render_image(img, alpha), *fmt)
                    cache[n] = (frame, hash(image._size))

                if unset_size:
                    image._size = None

                yield frame
                n += 1
                image._seek_position = n

            image._seek_position = 0
            if repeat > 0:  # Avoid infinitely large negative numbers
                repeat -= 1

        # For consistency in behaviour
        if img is image._source:
            img.seek(0)


# Reserved
def _color(text: str, fg: tuple = (), bg: tuple = ()) -> str:
    """Prepends *text* with ANSI 24-bit color escape codes
    for the given foreground and/or background RGB values.

    The color code is ommited for any of *fg* or *bg* that is empty.
    """
    return (_FG_FMT * bool(fg) + _BG_FMT * bool(bg) + "%s") % (*fg, *bg, text)


# The pixel ratio is always used to adjust the width and not the height, so that the
# image can fill the terminal screen as much as possible.
# The final width is always rounded, but that should never be an issue
# since it's also rounded during size validation.
_pixel_ratio = 1.0  # Default
