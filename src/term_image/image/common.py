"""
.. Common Interfaces For Various Image Classes
"""

from __future__ import annotations

__all__ = ("ImageSource", "BaseImage", "GraphicsImage", "TextImage", "ImageIterator")

import io
import os
import re
import sys
import time
from abc import ABC, abstractmethod
from enum import Enum
from functools import wraps
from math import ceil
from operator import gt, mul, sub
from random import randint
from types import FunctionType, TracebackType
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

import PIL
import requests
from PIL import Image, UnidentifiedImageError

from .. import get_font_ratio
from ..exceptions import (
    InvalidSizeError,
    TermImageError,
    URLNotFoundError,
    _style_error,
)
from ..utils import (
    COLOR_RESET,
    CSI,
    ClassInstanceMethod,
    get_cell_size,
    get_fg_bg_colors,
    get_terminal_size,
    no_redecorate,
)

_ALPHA_THRESHOLD = 40 / 255  # Default alpha threshold
_FORMAT_SPEC = re.compile(
    r"(([<|>])?(\d+)?)?(\.([-^_])?(\d+)?)?(#(\.\d+|[0-9a-f]{6}|#)?)?(\+(.+))?",
    re.ASCII,
)
_NO_VERTICAL_SPEC = re.compile(r"(([<|>])?(\d+)?)?\.(#(\.\d+|[0-9a-f]{6})?)?", re.ASCII)
_ALPHA_BG_FORMAT = re.compile("#([0-9a-f]{6})?", re.ASCII)


@no_redecorate
def _close_validated(func: FunctionType) -> FunctionType:
    """Enables finalization status validation before performing an operation with a
    `BaseImage` instance.
    """

    @wraps(func)
    def close_validated_wrapper(self, *args, **kwargs):
        if self._closed:
            raise TermImageError("This image has been finalized")
        return func(self, *args, **kwargs)

    return close_validated_wrapper


class ImageSource(Enum):
    """Image source type.

    NOTE:
        The values of the enumeration members are implementation details and might
        change at anytime.
        Any comparison should be by identity of the members themselves.
    """

    class _SourceAttr(str):
        """A string that only compares equal to itself but returns the original hash of
        the string.

        Used to store the attribute that holds the value for ``image.source`` as the
        value of enum members, because some would normally compare equal.
        """

        def __init__(self, *_):
            self._str = super().__str__()

        def __eq__(*_):
            return NotImplemented

        def __repr__(self):
            return "<hidden>"

        __hash__ = str.__hash__
        __ne__ = __eq__
        __ascii__ = __str__ = __repr__

    #: The instance was derived from a path to a local image file.
    FILE_PATH = _SourceAttr("_source")

    #: The instance was derived from a PIL image instance.
    PIL_IMAGE = _SourceAttr("_source")

    #: The instance was derived from an image URL.
    URL = _SourceAttr("_url")


class BaseImage(ABC):
    """Base of all render styles.

    Args:
        image: Source image.
        width: Horizontal dimension of the image, in columns.
        height: Vertical dimension of the image, in lines.
        scale: The fraction of the size on respective axes, to render the image with.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.

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
        * For animated images, the seek position is initialized to the current seek
          position of the given image.

    ATTENTION:
        This class cannot be directly instantiated. Image instances should be created
        from its subclasses.
    """

    # Data Attributes

    _supported: Optional[bool] = None
    _render_method: Optional[str] = None
    _render_methods: Set[str] = set()
    _style_args: Dict[
        str, Tuple[Tuple[FunctionType, str], Tuple[FunctionType, str]]
    ] = {}

    # Special Methods

    def __init__(
        self,
        image: PIL.Image.Image,
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        scale: Tuple[float, float] = (1.0, 1.0),
    ) -> None:
        """See the class description"""
        if not isinstance(image, Image.Image):
            raise TypeError(
                "Expected a 'PIL.Image.Image' instance for 'image' "
                f"(got: {type(image).__name__!r})."
            )

        self._closed = False
        self._source = image
        self._source_type = ImageSource.PIL_IMAGE
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
            self._seek_position = image.tell()
            self._n_frames = None

        # Recognized sizing parameters.
        # These are initialized here only to avoid `AttributeError`s in case `_size` is
        # initially set via a means other than `set_size()`.
        self._fit_to_width = False
        self._h_allow = 0
        self._v_allow = 2  # A 2-line allowance for the shell prompt, etc

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> BaseImage:
        return self

    def __exit__(self, typ: type, val: Exception, tb: TracebackType) -> bool:
        self.close()
        return False  # Currently, no particular exception is suppressed

    def __format__(self, spec: str) -> str:
        """Renders the image with alignment, padding and transparency control"""
        # Only the currently set frame is rendered for animated images
        h_align, width, v_align, height, alpha, style_args = self._check_format_spec(
            spec
        )

        return self._format_render(
            self._renderer(self._render_image, alpha, **style_args),
            h_align,
            width,
            v_align,
            height,
        )

    def __iter__(self) -> ImageIterator:
        return ImageIterator(self, 1, "1.1", False)

    def __repr__(self) -> str:
        return "<{}: source_type={} size={} scale={} is_animated={}>".format(
            type(self).__name__,
            self._source_type.name,
            self._size and "x".join(map(str, self._size)),
            "x".join(format(x, ".2") for x in self._scale),
            self._is_animated,
        )

    def __str__(self) -> str:
        """Renders the image with transparency enabled and without alignment"""
        # Only the currently set frame is rendered for animated images
        return self._renderer(self._render_image, _ALPHA_THRESHOLD)

    # Properties

    closed = property(
        lambda self: self._closed,
        doc="""Instance finalization status

        :rtype: bool
        """,
    )

    frame_duration = property(
        lambda self: self._frame_duration if self._is_animated else None,
        doc="""Duration (in seconds) of a single frame for :term:`animated` images

        Setting this on non-animated images is simply ignored, no exception is raised.

        :rtype: float
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

        :rtype: int
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
        """The number of frames in the image

        :rtype: int
        """
        if not self._is_animated:
            return 1

        if not self._n_frames:
            self._n_frames = self._get_image().n_frames

        return self._n_frames

    rendered_height = property(
        lambda self: round(
            (self._size or self._valid_size(None, None))[1] * self._scale[1]
        ),
        doc="""
        The **scaled** height of the image.

        Also the exact number of lines that the drawn image will occupy in a terminal.

        :rtype: int
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

        :rtype: Tuple[int, int]
        """,
    )

    rendered_width = property(
        lambda self: round(
            (self._size or self._valid_size(None, None))[0] * self._scale[0]
        ),
        doc="""
        The **scaled** width of the image.

        Also the exact number of columns that the drawn image will occupy in a terminal.

        :rtype: int
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

        :rtype: Tuple[float, float]
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

        :rtype: float
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

        :rtype: float
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

        :rtype: Tuple[int, int]
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
        _close_validated(lambda self: getattr(self, self._source_type.value)),
        doc="""
        The :term:`source` from which the instance was initialized.

        :rtype: Union[PIL.Image.Image, str]
        """,
    )

    source_type = property(
        lambda self: self._source_type,
        doc="""
        The kind of :term:`source` from which the instance was initialized.

        :rtype: ImageSource
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

        :rtype: int
        """,
    )

    # # Private

    @property
    @abstractmethod
    def _pixel_ratio(self):
        """The width-to-height ratio of a pixel drawn in the terminal"""
        raise NotImplementedError

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
                if self._source_type is ImageSource.URL:
                    try:
                        os.remove(self._source)
                    except FileNotFoundError:
                        pass
                    del self._url
                del self._source
        except AttributeError:
            pass  # Instance creation or initialization was unsuccessful
        finally:
            self._closed = True

    def draw(
        self,
        h_align: Optional[str] = None,
        pad_width: Optional[int] = None,
        v_align: Optional[str] = None,
        pad_height: Optional[int] = None,
        alpha: Optional[float, str] = _ALPHA_THRESHOLD,
        *,
        scroll: bool = False,
        animate: bool = True,
        repeat: int = -1,
        cached: Union[bool, int] = 100,
        check_size: bool = True,
        **style: Any,
    ) -> None:
        """Draws an image to standard output.

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

              * If ``None``, transparency is disabled (alpha channel is removed).
              * If a ``float`` (**0.0 <= x < 1.0**), specifies the alpha ratio
                **above** which pixels are taken as **opaque**. **(Applies to only
                text-based render styles)**.
              * If a string, specifies a color to replace transparent background with.
                Can be:

                * **"#"** -> The terminal's default background color (or black, if
                  undetermined) is used.
                * A hex color e.g ``ffffff``, ``7faa52``.

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

              * If ``bool``, it directly sets if the frames will be cached or not.
              * If ``int``, caching is enabled only if the framecount of the image
                is less than or equal to the given number.

            check_size: If ``False``, does not perform size validation for
              non-animations.
            style: Style-specific parameters. See each subclass for it's own usage.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
            ValueError: Unable to convert image.
            ValueError: Image size or :term:`scale` too small.
            term_image.exceptions.InvalidSizeError: The image's :term:`rendered size`
              can not fit into the :term:`available terminal size <available size>`.
            term_image.exceptions.StyleError: Unrecognized style-specific parameter(s).

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
          * **with the exception of native animations provided by some render styles**.

        * Animations, **by default**, are infinitely looped and can be terminated
          with **Ctrl+C** (``SIGINT``), raising ``KeyboardInterrupt``.
        """
        fmt = self._check_formatting(h_align, pad_width, v_align, pad_height)

        if alpha is not None:
            if isinstance(alpha, float):
                if not 0.0 <= alpha < 1.0:
                    raise ValueError(f"Alpha threshold out of range (got: {alpha})")
            elif isinstance(alpha, str):
                if not _ALPHA_BG_FORMAT.fullmatch(alpha):
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
            not style.get("native")
            and self._is_animated
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

        def render(image: PIL.Image.Image) -> None:
            # Hide the cursor immediately if the output is a terminal device
            sys.stdout.isatty() and print(f"{CSI}?25l", end="", flush=True)
            try:
                style_args = self._check_style_args(style)
                if self._is_animated and animate:
                    self._display_animated(
                        image, alpha, fmt, repeat, cached, **style_args
                    )
                else:
                    try:
                        print(
                            self._format_render(
                                self._render_image(image, alpha, **style_args),
                                *fmt,
                            ),
                            end="",
                            flush=True,
                        )
                    except (KeyboardInterrupt, Exception):
                        self._handle_interrupted_draw()
                        raise
            finally:
                # Reset color and show the cursor
                print(COLOR_RESET, f"{CSI}?25h" * sys.stdout.isatty(), sep="")

        self._renderer(
            render,
            scroll=scroll,
            check_size=check_size,
            animated=not style.get("native") and self._is_animated and animate,
        )

    @classmethod
    def from_file(
        cls,
        filepath: str,
        **kwargs: Union[None, int, Tuple[float, float]],
    ) -> BaseImage:
        """Creates an instance from an image file.

        Args:
            filepath: Relative/Absolute path to an image file.
            kwargs: Same keyword arguments as the class constructor.

        Returns:
            A new instance.

        Raises:
            TypeError: *filepath* is not a string.
            FileNotFoundError: The given path does not exist.
            IsADirectoryError: Propagated from from ``PIL.Image.open()``.
            PIL.UnidentifiedImageError: Propagated from from ``PIL.Image.open()``.

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
        new._source_type = ImageSource.FILE_PATH
        return new

    @classmethod
    def from_url(
        cls,
        url: str,
        **kwargs: Union[None, int, Tuple[float, float]],
    ) -> BaseImage:
        """Creates an instance from an image URL.

        Args:
            url: URL of an image file.
            kwargs: Same keyword arguments as the class constructor.

        Returns:
            A new instance.

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
        new._source_type = ImageSource.URL
        new._url = url
        return new

    @classmethod
    @abstractmethod
    def is_supported(cls) -> bool:
        """Returns ``True`` if the render style or graphics protocol implemented by
        the invoking class is supported by the :term:`active terminal`.
        Otherwise, ``False``.

        ATTENTION:
            Support checks for most (if not all) render styles require :ref:`querying
            <terminal-queries>` the :term:`active terminal`, though **only the first
            time** they're executed.

            Hence, it's advisable to perform all neccesary support checks (call
            ``is_supported()`` on required subclasses) at an early stage of a program,
            before user input is required.
        """
        raise NotImplementedError

    def seek(self, pos: int) -> None:
        """Changes current image frame.

        Args:
            pos: New frame number.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.

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

    @ClassInstanceMethod
    def set_render_method(self_or_cls, method: Optional[str] = None) -> None:
        """Sets the render method used by the instances of subclasses providing
        multiple render methods.

        Args:
            method: The render method to be set or ``None`` for a reset
              (case-insensitive).

        Raises:
            TypeError: *method* is not a string or ``None``.
            ValueError: the given method is not implmented by the invoking class
              (or class of the invoking instance).

        See the **Render Methods** section in the description of the subclasses that
        implement such for their specific usage.

        If called via:

           - a class, sets the class-wide render method.
           - an instance, sets the instance-specific render method.

        If *method* is ``None`` and this method is called via:

           - a class, the class-wide render method is reset to the default.
           - an instance, the instance-specific render method is removed, so that it
             uses the class-wide render method thenceforth.

        Any instance without a specific render method set uses the class-wide render
        method.

        NOTE:
            *method* = ``None`` is always allowed, even if the render style doesn't
            implement multiple render methods.
        """
        if method is not None and not isinstance(method, str):
            raise TypeError(
                f"'method' must be a string or `None` (got: {type(method).__name__!r})"
            )

        if method is not None and method.lower() not in self_or_cls._render_methods:
            cls = (
                type(self_or_cls) if isinstance(self_or_cls, __class__) else self_or_cls
            )
            raise ValueError(f"Unknown render method {method!r} for {cls.__name__}")

        if not method:
            if isinstance(self_or_cls, __class__):
                try:
                    del self_or_cls._render_method
                except AttributeError:
                    pass
            elif self_or_cls._render_methods:
                self_or_cls._render_method = self_or_cls._default_render_method
        else:
            self_or_cls._render_method = method

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
            term_image.exceptions.InvalidSizeError: *maxsize* is given and the
              resulting size will not fit into it.

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
               :py:exc:`term_image.exceptions.InvalidSizeError` if such is the case.

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

    @classmethod
    def _check_format_spec(
        cls, spec: str
    ) -> Tuple[
        Optional[str],
        Optional[int],
        Optional[str],
        Optional[int],
        Union[None, float, str],
        Dict[str, Any],
    ]:
        """Validates a format specifier and translates it into the required values.

        Returns:
            A tuple ``(h_align, width, v_align, height, alpha, style_args)`` containing
            values as required by ``_format_render()`` and ``_render_image()``.
        """
        match_ = _FORMAT_SPEC.fullmatch(spec)
        if not match_ or _NO_VERTICAL_SPEC.fullmatch(spec):
            raise ValueError(f"Invalid format specifier (got: {spec!r})")

        (
            _,
            h_align,
            width,
            _,
            v_align,
            height,
            alpha,
            threshold_or_bg,
            _,
            style_spec,
        ) = match_.groups()

        return (
            *cls._check_formatting(
                h_align, width and int(width), v_align, height and int(height)
            ),
            (
                threshold_or_bg
                and (
                    "#" + threshold_or_bg.lstrip("#")
                    if _ALPHA_BG_FORMAT.fullmatch("#" + threshold_or_bg.lstrip("#"))
                    else float(threshold_or_bg)
                )
                if alpha
                else _ALPHA_THRESHOLD
            ),
            style_spec and cls._check_style_format_spec(style_spec, style_spec) or {},
        )

    @staticmethod
    def _check_formatting(
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

    @classmethod
    def _check_style_args(cls, style_args: Dict[str, Any]) -> Dict[str, Any]:
        """Validates style-specific arguments and translates them into the required
        values.

        Removes any argument having a value equal to the default.

        Returns:
            A mapping of keyword arguments.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
            term_image.exceptions.StyleError: An unknown style-specific parameter is
              given.
        """
        for name, value in tuple(style_args.items()):
            try:
                (
                    default,
                    (check_type, type_msg),
                    (check_value, value_msg),
                ) = cls._style_args[name]
            except KeyError:
                for other_cls in cls.__mro__:
                    # less costly than memebership tests on every class' __bases__
                    if other_cls is __class__:
                        raise _style_error(cls)(
                            f"Unknown style-specific parameter {name!r}"
                        )

                    if not issubclass(
                        other_cls, __class__
                    ) or "_style_args" not in vars(other_cls):
                        continue

                    try:
                        (check_type, type_msg), (check_value, value_msg) = super(
                            other_cls, cls
                        )._style_args[name]
                        break
                    except KeyError:
                        pass
                else:
                    raise _style_error(cls)(
                        f"Unknown style-specific parameter {name!r}"
                    )

            if not check_type(value):
                raise TypeError(f"{type_msg} (got: {type(value).__name__})")
            if not check_value(value):
                raise ValueError(f"{value_msg} (got: {value!r})")

            # Must not occur before type and value checks to avoid falling prey of
            # operator overloading
            if value == default:
                del style_args[name]

        return style_args

    @classmethod
    def _check_style_format_spec(cls, spec: str, original: str) -> Dict[str, Any]:
        """Validates a style-specific format specifier and translates it into
        the required values.

        Returns:
            A mapping of keyword arguments.

        Raises:
            term_image.exceptions.StyleError: Invalid style-specific format specifier.

        **Every style-specific format spec should be handled as follows:**

        Every overriding method should call the overriden method (more on this below).
        At every step in the call chain, the specifier should be of the form::

            [parent] [current] [invalid]

        where:

        - *parent* is the portion to be interpreted at an higher level in the chain
        - *current* is the portion to be interpreted at the current level in the chain
        - the *invalid* portion determines the validity of the format spec

        Handle the portions in the order *invalid*, *parent*, *current*, so that
        validity can be determined before any further processing.

        At any point in the chain where the *invalid* portion exists (i.e is non-empty),
        the format spec can be correctly taken to be invalid.

        An overriding method must call the overridden method with the *parent* portion
        and the original format spec, **if** *parent* **is not empty**, such that every
        successful check ends up at `BaseImage._check_style_args()` or when *parent* is
        empty.

        :py:meth:`_get_style_format_spec` can (optionally) be used to parse the format
        spec at each level of the call chain.
        """
        if spec:
            raise _style_error(cls)(
                f"Invalid style-specific format specifier {original!r}"
                + (f", detected at {spec!r}" if spec != original else "")
            )
        return {}

    @staticmethod
    def _clear_frame() -> bool:
        """Clear the animation frame on-screen, if necessary.

        Used by some graphics-based styles.

        Returns:
            ``True`` if the frame was cleared. Otherwise, ``False``.
        """
        return False

    @staticmethod
    def _clear_images() -> bool:
        """Clear images on-screen.

        Used by some graphics-based styles.

        Any overriding method should return ``True``.
        """
        return False

    def _display_animated(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        fmt: Tuple[Union[None, str, int]],
        repeat: int,
        cached: Union[bool, int],
        **style_args: Any,
    ) -> None:
        """Displays an animated GIF image in the terminal.

        NOTE:
            This is done indefinitely but can be terminated with ``Ctrl-C``
            (``SIGINT``), raising ``KeyboardInterrupt``.
        """
        lines = max(
            (fmt or (None,))[-1] or get_terminal_size()[1] - self._v_allow,
            self.rendered_height,
        )
        prev_seek_pos = self._seek_position
        duration = self._frame_duration
        image_it = ImageIterator(self, repeat, "", cached)
        image_it._animator = image_it._animate(img, alpha, fmt, style_args)

        try:
            print(next(image_it._animator), end="", flush=True)  # First frame

            # Render next frame during current frame's duration
            start = time.time()
            for frame in image_it._animator:  # Renders next frame
                # Left-over of current frame's duration
                time.sleep(max(0, duration - (time.time() - start)))

                # Clear the current frame, if necessary,
                # move cursor up to the begining of the first line of the image
                # and print the new current frame.
                self._clear_frame()
                print(f"\r{CSI}{lines - 1}A", frame, sep="", end="", flush=True)

                # Render next frame during current frame's duration
                start = time.time()
        except (KeyboardInterrupt, Exception):
            self._handle_interrupted_draw()
            raise
        finally:
            if img is not self._source:
                img.close()
            image_it.close()
            self._seek_position = prev_seek_pos
            # Move the cursor to the last line of the image to prevent "overlayed"
            # output in the terminal
            print(f"{CSI}{lines}B", end="")

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
        cols, rows = self.rendered_size

        width = width or get_terminal_size()[0] - self._h_allow
        if width > cols:
            if h_align == "<":  # left
                left = ""
                right = " " * (width - cols)
            elif h_align == ">":  # right
                left = " " * (width - cols)
                right = ""
            else:  # center
                left = " " * ((width - cols) // 2)
                right = " " * (width - cols - len(left))
            render = render.replace("\n", f"{right}\n{left}")
        else:
            left = right = ""

        height = height or get_terminal_size()[1] - self._v_allow
        if height > rows:
            if v_align == "^":  # top
                top = 0
                bottom = height - rows
            elif v_align == "_":  # bottom
                top = height - rows
                bottom = 0
            else:  # middle
                top = (height - rows) // 2
                bottom = height - rows - top

            line = f"{' ' * width}\n"
            top = line * top
            bottom = line * bottom
        else:
            top = bottom = ""

        return (
            "".join((top, left, render, right, bottom))
            if width > cols or height > rows
            else render
        )

    @_close_validated
    def _get_image(self) -> PIL.Image.Image:
        """Returns the PIL image instance corresponding to the image source as-is"""
        return (
            Image.open(self._source) if isinstance(self._source, str) else self._source
        )

    def _get_render_data(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        size: Optional[Tuple[int, int]] = None,
        pixel_data: bool = True,
        round_alpha: bool = False,
        frame: bool = False,
    ) -> Tuple[
        PIL.Image.Image, Optional[List[Tuple[int, int, int]]], Optional[List[int]]
    ]:
        """Returns the PIL image instance and pixel data required to render an image.

        Args:
            size: If given (in pixels), it is used instead of the pixel-equivalent of
              the image size (or auto size, if size is unset).
            pixel_data: If ``False``, ``None`` is returned for all pixel data.
            round_alpha: Only applies when *alpha* is a ``float``.

              If ``True``, returned alpha values are bi-level (``0`` or ``255``), based
              on the given alpha threshold.
              Also, the image is blended with the active terminal's BG color (or black,
              if undetermined) while leaving the alpha intact.

            frame: If ``True``, implies *img* is being used by ``ImageIterator``,
              hence, *img* is not closed.

        The returned image is appropriately converted, resized and composited
        (if need be).

        The pixel data are the last two items of the returned tuple ``(rgb, a)``, where:
          * ``rgb`` is a list of ``(r, g, b)`` tuples containing the colour channels of
            the image's pixels in a flattened row-major order where ``r``, ``g``, ``b``
            are integers in the range [0, 255].
          * ``a`` is a list of integers in the range [0, 255] representing the alpha
            channel of the image's pixels in a flattened row-major order.
        """

        def convert_resize_img(mode: str):
            nonlocal img

            if img.mode != mode:
                prev_img = img
                try:
                    img = img.convert(mode)
                except Exception as e:
                    raise ValueError("Unable to convert image") from e
                finally:
                    if frame_img is not prev_img is not self._source:
                        prev_img.close()

            if img.size != size:
                prev_img = img
                try:
                    img = img.resize(size, Image.Resampling.BOX)
                except ValueError as e:
                    raise ValueError("Image size or scale too small") from e
                finally:
                    if frame_img is not prev_img is not self._source:
                        prev_img.close()

        frame_img = img if frame else None
        if self._is_animated:
            img.seek(self._seek_position)
        if not size:
            size = self._get_render_size()

        if alpha is None or img.mode in {"1", "L", "RGB", "HSV", "CMYK"}:
            convert_resize_img("RGB")
            if pixel_data:
                rgb = list(img.getdata())
                a = [255] * mul(*size)
        else:
            convert_resize_img("RGBA")
            if isinstance(alpha, str):
                if alpha == "#":
                    alpha = get_fg_bg_colors(hex=True)[1] or "#000000"
                bg = Image.new("RGBA", img.size, alpha)
                bg.alpha_composite(img)
                if img is not self._source:
                    img.close()
                img = bg.convert("RGB")
                if pixel_data:
                    a = [255] * mul(*size)
            else:
                if pixel_data:
                    a = list(img.getdata(3))
                    if round_alpha:
                        alpha = round(alpha * 255)
                        a = [0 if val < alpha else 255 for val in a]
                if round_alpha:
                    bg = Image.new(
                        "RGBA", img.size, get_fg_bg_colors(hex=True)[1] or "#000000"
                    )
                    bg.alpha_composite(img)
                    bg.putalpha(img.getchannel("A"))
                    if img is not self._source:
                        img.close()
                    img = bg

            if pixel_data:
                rgb = list((img if img.mode == "RGB" else img.convert("RGB")).getdata())

        return (img, *(pixel_data and (rgb, a) or (None, None)))

    @abstractmethod
    def _get_render_size(self) -> Tuple[int, int]:
        """Returns the size (in pixels) required to render the image.

        Applies the image scale.
        """
        raise NotImplementedError

    @staticmethod
    def _handle_interrupted_draw():
        """Performs any neccessary actions when image drawing is interrupted."""

    @classmethod
    def _get_style_format_spec(
        cls, spec: str, original: str
    ) -> Tuple[str, List[Union[None, str, Tuple[Optional[str]]]]]:
        """Parses a style-specific format specifier.

        See :py:meth:`_check_format_spec`.

        Returns:
            The *parent* portion and a list of matches for the respective fields of the
            *current* portion of the spec.

            * Any absent field of *current* is ``None``.
            * For a field containing groups, the match, if present, is a tuple
              containing the full match followed by the matches for each group.
            * All matches are in the same order as the fields (including their groups).

        Raises:
            term_image.exceptions.StyleError: The *invalid* portion exists.

        NOTE:
            Please avoid common fields in the format specs of parent and child classes
            (i.e fields that can match the same portion of a given string) as they
            result in ambiguities.
        """
        patterns = iter(cls._FORMAT_SPEC)
        fields = []
        for pattern in patterns:
            match = pattern.search(spec)
            if match:
                fields.append(
                    (match.group(), *match.groups())
                    if pattern.groups
                    else match.group()
                )
                start = match.start()
                end = match.end()
                break
            else:
                fields.append(
                    (None,) * (pattern.groups + 1) if pattern.groups else None
                )
        else:
            start = end = len(spec)

        for pattern in patterns:
            match = pattern.match(spec, pos=end)
            if match:
                fields.append(
                    (match.group(), *match.groups())
                    if pattern.groups
                    else match.group()
                )
                end = match.end()
            else:
                fields.append(
                    (None,) * (pattern.groups + 1) if pattern.groups else None
                )

        parent, invalid = spec[:start], spec[end:]
        if invalid:
            raise _style_error(cls)(
                f"Invalid style-specific format specifier {original!r}"
                f", detected at {invalid!r}"
            )

        return parent, fields

    @staticmethod
    @abstractmethod
    def _pixels_cols(
        *, pixels: Optional[int] = None, cols: Optional[int] = None
    ) -> int:
        """Returns the number of pixels represented by a given number of columns
        or vice-versa.
        """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def _pixels_lines(
        *, pixels: Optional[int] = None, lines: Optional[int] = None
    ) -> int:
        """Returns the number of pixels represented by a given number of lines
        or vice-versa.
        """
        raise NotImplementedError

    @abstractmethod
    def _render_image(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        frame: bool = False,  # For `ImageIterator`
    ) -> str:
        """Converts an image into a string which reproduces the image when printed
        to the terminal.

        NOTE:
            This method is not meant to be used directly, use it via `_renderer()`
            instead.
        """
        raise NotImplementedError

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
            renderer: The function to perform the specific rendering operation for the
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
            term_image.exceptions.InvalidSizeError: *check_size* or *animated* is
              ``True`` and the image's :term:`rendered size` can not fit into the
              :term:`available terminal size <available size>`.
            term_image.exceptions.TermImageError: The image has been finalized.

        NOTE:
            If the ``set_size()`` method was previously used to set the image size,
            (directly or not), the last value of its *fit_to_width* parameter
            is taken into consideration, for non-animations.
        """
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
                    raise InvalidSizeError(
                        "The "
                        + ("animation" if animated else "image")
                        + " cannot fit into the available terminal size"
                    )

                # Reaching here means it's either valid or *_fit_to_width* and/or
                # *scroll* is/are `True`.
                if animated and self.rendered_height > lines:
                    raise InvalidSizeError(
                        "The rendered height cannot be greater than the terminal "
                        "height for animations"
                    )

            return renderer(self._get_image(), *args, **kwargs)

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
                        pixels=round(
                            self._width_height_px(w=max_width) * self._pixel_ratio
                        )
                    ),
                )
            if fit_to_height:
                return (
                    self._pixels_cols(
                        pixels=round(
                            self._width_height_px(h=max_height) / self._pixel_ratio
                        )
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
                _height_px = _height_px * self._pixel_ratio
                # If height becomes greater than the max, reduce it to the max
                height_px = min(_height_px, max_height)
                # Calculate the corresponding width
                width_px = round((height_px / _height_px) * _width_px)
                # Round the height
                height_px = round(height_px)
            else:
                _width_px = _width_px / self._pixel_ratio
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
                self._width_height_px(h=self._pixels_lines(lines=height))
                / self._pixel_ratio
            )
            width = self._pixels_cols(pixels=width_px)
        elif height is None:
            height_px = round(
                self._width_height_px(w=self._pixels_cols(cols=width))
                * self._pixel_ratio
            )
            height = self._pixels_lines(pixels=height_px)

        if maxsize and (width > columns or height > lines):
            raise InvalidSizeError(
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


class GraphicsImage(BaseImage):
    """Base of all render styles using terminal graphics protocols.

    Raises:
        term_image.exceptions.StyleError: The :term:`active terminal` doesn't support
          the render style.

    See :py:class:`BaseImage` for the description of the constructor.

    ATTENTION:
        This class cannot be directly instantiated. Image instances should be created
        from its subclasses.
    """

    # Size unit conversion already involves cell size calculation
    _pixel_ratio: float = 1.0

    def __init__(self, image: PIL.Image.Image, **kwargs) -> None:
        if not self.is_supported():
            raise _style_error(type(self))(
                "This image render style is not supported in the active terminal"
            )
        super().__init__(image, **kwargs)

    def _get_minimal_render_size(self, *, adjust: bool) -> Tuple[int, int]:
        render_size = self._get_render_size()
        r_height = self.rendered_height
        width, height = (
            render_size
            if mul(*render_size) < mul(*self._original_size)
            else self._original_size
        )

        # When `_original_size` is used, ensure the height is a multiple of the rendered
        # height, so that pixels can be evenly distributed among all lines.
        # If r_height == 0, height == 0, extra == 0; Handled in `_get_render_data()`.
        if adjust:
            extra = height % (r_height or 1)
            if extra:
                # Incremented to the greater multiple to avoid losing any data
                height = height - extra + r_height

        return width, height

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


class TextImage(BaseImage):
    """Base of all render styles using ASCII/Unicode symbols [with ANSI color codes].

    See :py:class:`BaseImage` for the description of the constructor.

    IMPORTANT:
        Instantiation of subclasses is always allowed, even if the current terminal
        does not [fully] support the render style.

        To check if the render style is fully supported in the current terminal, use
        :py:meth:`is_supported() <BaseImage.is_supported>`.

    ATTENTION:
        This class cannot be directly instantiated. Image instances should be created
        from its subclasses.
    """

    # Pixels are represented in a 1-to-2 ratio within one character cell
    # pixel-size == width * height/2
    # pixel-ratio == width / (height/2) == 2 * (width / height) == 2 * font-ratio
    _pixel_ratio = property(lambda _: get_font_ratio() * 2)


class ImageIterator:
    """Effeciently iterate over :term:`rendered` frames of an :term:`animated` image

    Args:
        image: Animated image.
        repeat: The number of times to go over the entire image. A negative value
          implies infinite repetition.
        format: The :ref:`format specifier <format-spec>` to be used to format the
          rendered frames (default: auto).
        cached: Determines if the :term:`rendered` frames will be cached (for speed up
          of subsequent renders) or not.

          * If ``bool``, it directly sets if the frames will be cached or not.
          * If ``int``, caching is enabled only if the framecount of the image
            is less than or equal to the given number.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.
        term_image.exceptions.StyleError: Invalid style-specific format specifier.

    * If *repeat* equals ``1``, caching is disabled.
    * The iterator has immediate response to changes in the image size
      and :term:`scale`.
    * If the image size is :ref:`unset <unset-size>`, it's automatically
      calculated per frame.
    * The number of the last yielded frame is set as the image's seek position.
    * Directly adjusting the seek position of the image doesn't affect iteration.
      Use :py:meth:`ImageIterator.seek` instead.
    * After the iterator is exhausted, the underlying image is set to frame ``0``.
    """

    def __init__(
        self,
        image: BaseImage,
        repeat: int = -1,
        format: str = "",
        cached: Union[bool, int] = 100,
    ) -> None:
        if not isinstance(image, BaseImage):
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
        *fmt, alpha, style_args = image._check_format_spec(format)

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
        self._loop_no = None
        self._animator = image._renderer(
            self._animate, alpha, fmt, style_args, check_size=False
        )

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
        return "{}(image={!r}, repeat={}, format={!r}, cached={}, loop_no={})".format(
            type(self).__name__,
            *self.__dict__.values(),
        )

    loop_no = property(
        lambda self: self._loop_no,
        doc="""Iteration repeat countdown

        Changes on the first iteration of each loop, except for infinite iteration
        where it's always ``-1``.
        """,
    )

    def close(self) -> None:
        """Closes the iterator and releases resources used.

        Does not reset the frame number of the underlying image.

        NOTE:
            This method is automatically called when the iterator is exhausted or
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

    def seek(self, pos: int) -> None:
        """Sets the frame number to be yielded on the next iteration without affecting
        the repeat count.

        Args:
            pos: Next frame number.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
            term_image.exceptions.TermImageError: The iterator is unused.

        Frame numbers start from ``0`` (zero).
        """
        if not isinstance(pos, int):
            raise TypeError(f"Invalid frame number type (got: {type(pos).__name__})")
        if not 0 <= pos < self._image.n_frames:
            raise ValueError(
                "Frame number out of range "
                f"(got: {pos}, n_frames={self._image._n_frames})"
            )

        try:
            self._animator.send(pos)
        except TypeError:
            raise TermImageError("Iteration has not yet started") from None

    def _animate(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        fmt: Tuple[Union[None, str, int]],
        style_args: Dict[str, Any],
    ) -> None:
        """Returns a generator that yields rendered and formatted frames of the
        underlying image.
        """
        self._img = img  # For cleanup
        image = self._image
        cached = self._cached
        self._loop_no = repeat = self._repeat
        if cached:
            cache = [(None,) * 2] * image.n_frames

        sent = None
        n = 0
        while repeat:
            if sent is None:
                # Size must be set before hashing, since `None` will always
                # compare equal but doesn't mean the size is the same.
                unset_size = not image._size
                if unset_size:
                    image.set_size()

                image._seek_position = n
                try:
                    frame = image._format_render(
                        image._render_image(img, alpha, frame=True, **style_args), *fmt
                    )
                except EOFError:
                    image._seek_position = n = 0
                    if repeat > 0:  # Avoid infinitely large negative numbers
                        self._loop_no = repeat = repeat - 1
                    if cached:
                        break
                    continue
                else:
                    if cached:
                        cache[n] = (frame, hash(image._size))
                finally:
                    if unset_size:
                        image._size = None

            sent = yield frame
            n = n + 1 if sent is None else sent - 1

        if cached:
            n_frames = len(cache)
        while repeat:
            while n < n_frames:
                if sent is None:
                    # Size must be set before hashing, since `None` will always
                    # compare equal but doesn't mean the size is the same.
                    unset_size = not image._size
                    if unset_size:
                        image.set_size()

                    image._seek_position = n
                    frame, size_hash = cache[n]
                    if hash(image._size) != size_hash:
                        frame = image._format_render(
                            image._render_image(img, alpha, frame=True, **style_args),
                            *fmt,
                        )
                        cache[n] = (frame, hash(image._size))

                    if unset_size:
                        image._size = None

                sent = yield frame
                n = n + 1 if sent is None else sent - 1

            image._seek_position = n = 0
            if repeat > 0:  # Avoid infinitely large negative numbers
                self._loop_no = repeat = repeat - 1

        # For consistency in behaviour
        if img is image._source:
            img.seek(0)
