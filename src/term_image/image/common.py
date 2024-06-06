"""
.. Common Interfaces For Various Image Classes
"""

from __future__ import annotations

__all__ = (
    "ImageSource",
    "Size",
    "BaseImage",
    "GraphicsImage",
    "TextImage",
    "ImageIterator",
)

import atexit
import io
import os
import re
import sys
import time
from abc import ABCMeta, abstractmethod
from enum import Enum
from functools import wraps
from math import ceil
from operator import gt, mul
from shutil import rmtree
from tempfile import mkdtemp, mkstemp
from types import FunctionType, TracebackType
from typing import Any, Dict, Generator, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

import PIL
import requests
from PIL import Image, UnidentifiedImageError

from .. import get_cell_ratio
from ..ctlseqs import CURSOR_DOWN, CURSOR_UP, HIDE_CURSOR, SGR_NORMAL, SHOW_CURSOR
from ..exceptions import (
    InvalidSizeError,
    RenderError,
    StyleError,
    TermImageError,
    URLNotFoundError,
)
from ..utils import (
    XTERM_256_PALETTE,
    ClassInstanceMethod,
    ClassProperty,
    arg_type_error,
    arg_value_error,
    arg_value_error_msg,
    arg_value_error_range,
    cached,
    get_cell_size,
    get_fg_bg_colors,
    get_terminal_name_version,
    get_terminal_size,
    no_redecorate,
)

_ALPHA_THRESHOLD = 40 / 255  # Default alpha threshold
_FORMAT_SPEC = re.compile(
    r"(([<|>])?(\d+)?)?(\.([-^_])?(\d+)?)?(#(\.\d+|[0-9a-fA-F]{6}|#)?)?(\+(.+))?",
    re.ASCII,
)
_NO_VERTICAL_SPEC = re.compile(
    r"(([<|>])?(\d+)?)?\.(#(\.\d+|[0-9a-fA-F]{6})?)?", re.ASCII
)
_ALPHA_BG_FORMAT = re.compile("#([0-9a-fA-F]{6})?", re.ASCII)
_TEMP_DIR = mkdtemp()


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


class Hidden:
    """An object that hides it's original value representation."""

    def __repr__(_):
        return "<...>"

    __ascii__ = __str__ = __repr__


class SourceAttr(Hidden, str):
    """A string that only compares equal to itself but returns the original hash of
    the string.

    Used to store the name of the attribute that holds the value for
    :py:attr:`BaseImage.source`` as the value of enum members, because some would
    normally compare equal.
    """

    def __init__(self, *_):
        self._str = super(Hidden).__str__()

    def __eq__(self, _):
        return NotImplemented

    __ne__ = __eq__
    __hash__ = str.__hash__


class ImageSource(Enum):
    """Image source type."""

    #: The instance was derived from a path to a local image file.
    #:
    #: :meta hide-value:
    FILE_PATH = SourceAttr("_source")

    #: The instance was derived from a PIL image instance.
    #:
    #: :meta hide-value:
    PIL_IMAGE = SourceAttr("_source")

    #: The instance was derived from an image URL.
    #:
    #: :meta hide-value:
    URL = SourceAttr("_url")


class Size(Enum):
    """Enumeration for :term:`automatic sizing`."""

    #: Equivalent to :py:attr:`ORIGINAL` if it will fit into the
    #: :term:`frame size`, else :py:attr:`FIT`.
    #:
    #: :meta hide-value:
    AUTO = Hidden()

    #: The image size is set to fit optimally **within** the :term:`frame size`.
    #:
    #: :meta hide-value:
    FIT = Hidden()

    #: The size is set such that the width is exactly the :term:`frame width`,
    #: regardless of the :term:`cell ratio`.
    #:
    #: :meta hide-value:
    FIT_TO_WIDTH = Hidden()

    #: The image size is set such that the image is rendered with as many pixels as the
    #: the original image consists of.
    #:
    #: :meta hide-value:
    ORIGINAL = Hidden()


class ImageMeta(ABCMeta):
    """Type of all render style classes."""

    _forced_support: bool = False

    forced_support = ClassProperty(
        lambda self: self._forced_support,
        doc="""Forced render style support

        See the base instance of this metaclass for the complete description.
        """,
    )

    @forced_support.setter
    def forced_support(self, status: bool):
        if not isinstance(status, bool):
            raise arg_type_error("forced_support", status)

        self._forced_support = status


class BaseImage(metaclass=ImageMeta):
    """Base of all render styles.

    Args:
        image: Source image.
        width: Can be

          * a positive integer; horizontal dimension of the image, in columns.
          * a :py:class:`~term_image.image.Size` enum member.

        height: Can be

          * a positive integer; vertical dimension of the image, in lines.
          * a :py:class:`~term_image.image.Size` enum member.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.

    Propagates exceptions raised by :py:meth:`set_size`, if *width* or *height* is
    given.

    NOTE:
        * If neither *width* nor *height* is given (or both are ``None``),
          :py:attr:`~term_image.image.Size.FIT` applies.
        * If both width and height are not ``None``, they must be positive integers
          and :term:`manual sizing` applies i.e the image size is set as given without
          preserving aspect ratio.
        * For animated images, the seek position is initialized to the current seek
          position of the given image.
        * It's allowed to set properties for :term:`animated` images on non-animated
          ones, the values are simply ignored.

    ATTENTION:
        This class cannot be directly instantiated. Image instances should be created
        from its subclasses.
    """

    # Data Attributes

    _forced_support: bool = False
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
        width: Union[int, Size, None] = None,
        height: Union[int, Size, None] = None,
    ) -> None:
        """See the class description"""
        if not isinstance(image, Image.Image):
            raise arg_type_error("image", image)
        if 0 in image.size:
            raise ValueError("'image' is null-sized")

        self._closed = False
        self._source = image
        self._source_type = ImageSource.PIL_IMAGE
        self._original_size = image.size
        if width is None is height:
            self.size = Size.FIT
        else:
            self.set_size(width, height)

        self._is_animated = hasattr(image, "is_animated") and image.is_animated
        if self._is_animated:
            self._frame_duration = (image.info.get("duration") or 100) / 1000
            self._seek_position = image.tell()
            self._n_frames = None

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
        return "<{}: source_type={} size={} is_animated={}>".format(
            type(self).__name__,
            self._source_type.name,
            (
                self._size.name
                if isinstance(self._size, Size)
                else "x".join(map(str, self._size))
            ),
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

        :type: bool

        GET:
            Returns ``True`` if the instance has been finalized (:py:meth:`close` has
            been called). Otherwise, ``False``.
        """,
    )

    forced_support = ClassProperty(
        lambda self: type(self)._forced_support,
        doc="""Forced render style support

        :type: bool

        GET:
            Returns the forced support status of the invoking class or class of the
            invoking instance.

        SET:
            Forced support is enabled or disabled for the invoking class.

            Can not be set on an instance.

        If forced support is:

        * **enabled**, the render style is treated as if it were supported,
          regardless of the return value of :py:meth:`is_supported`.
        * **disabled**, the return value of :py:meth:`is_supported` determines if
          the render style is supported or not.

        By **default**, forced support is **disabled** for all render style classes.

        NOTE:
            * This property is :term:`descendant`.
            * This doesn't affect the return value of :py:meth:`is_supported` but
              may affect operations that require that a render style be supported e.g
              instantiation of some render style classes.
        """,
    )

    frame_duration = property(
        lambda self: self._frame_duration if self._is_animated else None,
        doc="""Duration of a single frame

        :type: Optional[float]

        GET:
            Returns:

            * The duration of a single frame (in seconds), if the image is animated.
            * ``None``, if otherwise.

        SET:
            If the image is animated, The frame duration is set.
            Otherwise, nothing is done.
        """,
    )

    @frame_duration.setter
    def frame_duration(self, value: float) -> None:
        if not isinstance(value, float):
            raise arg_type_error("frame_duration", value)
        if value <= 0.0:
            raise arg_value_error_range("frame_duration", value)
        if self._is_animated:
            self._frame_duration = value

    height = property(
        lambda self: self._size if isinstance(self._size, Size) else self._size[1],
        lambda self, height: self.set_size(height=height),
        doc="""
        Image height

        :type: Union[Size, int]

        GET:
            Returns:

            * The image height (in lines), if the image size is
              :term:`fixed <fixed size>`.
            * A :py:class:`~term_image.image.Size` enum member, if the image size
              is :term:`dynamic <dynamic size>`.

        SET:
            If set to:

            * a positive :py:class:`int`; the image height is set to the given value
              and the width is set proportionally.
            * a :py:class:`~term_image.image.Size` enum member; the image size is set
              as prescibed by the enum member.
            * ``None``; equivalent to :py:attr:`~term_image.image.Size.FIT`.

            This results in a :term:`fixed size`.
        """,
    )

    is_animated = property(
        lambda self: self._is_animated,
        doc="""
        Animatability of the image

        :type: bool

        GET:
            Returns ``True`` if the image is :term:`animated`. Otherwise, ``False``.
        """,
    )

    original_size = property(
        lambda self: self._original_size,
        doc="""Size of the source (in pixels)

        :type: Tuple[int, int]

        GET:
            Returns the source size.
        """,
    )

    @property
    def n_frames(self) -> int:
        """Image frame count

        :type: int

        GET:
            Returns the number of frames the image has.
        """
        if not self._is_animated:
            return 1

        if not self._n_frames:
            img = self._get_image()
            try:
                self._n_frames = img.n_frames
            finally:
                self._close_image(img)

        return self._n_frames

    rendered_height = property(
        lambda self: (
            self._valid_size(None, self._size)
            if isinstance(self._size, Size)
            else self._size
        )[1],
        doc="""
        The height with which the image is :term:`rendered`

        :type: int

        GET:
            Returns the number of lines the image will occupy when drawn in a terminal.
        """,
    )

    rendered_size = property(
        lambda self: (
            self._valid_size(self._size, None)
            if isinstance(self._size, Size)
            else self._size
        ),
        doc="""
        The size with which the image is :term:`rendered`

        :type: Tuple[int, int]

        GET:
            Returns the number of columns and lines (respectively) the image will
            occupy when drawn in a terminal.
        """,
    )

    rendered_width = property(
        lambda self: (
            self._valid_size(self._size, None)
            if isinstance(self._size, Size)
            else self._size
        )[0],
        doc="""
        The width with which the image is :term:`rendered`

        :type: int

        GET:
            Returns the number of columns the image will occupy when drawn in a
            terminal.
        """,
    )

    size = property(
        lambda self: self._size,
        doc="""
        Image size

        :type: Union[Size, Tuple[int, int]]

        GET:
            Returns:

            * The image size, ``(columns, lines)``, if the image size is
              :term:`fixed <fixed size>`.
            * A :py:class:`~term_image.image.Size` enum member, if the image size
              is :term:`dynamic <dynamic size>`.

        SET:
            If set to a:

            * :py:class:`~term_image.image.Size` enum member, the image size is set
              as prescibed by the given member.

              This results in a :term:`dynamic size` i.e the size is computed whenever
              the image is :term:`rendered` using the default :term:`frame size`.

            * 2-tuple of integers, ``(width, height)``, the image size set as given.

              This results in a :term:`fixed size` i.e the size will not change until
              it is re-set.
        """,
    )

    @size.setter
    def size(self, size: Size | Tuple[int, int]) -> None:
        if isinstance(size, Size):
            self._size = size
        elif isinstance(size, tuple):
            if len(size) != 2:
                raise arg_value_error("size", size)
            self.set_size(*size)
        else:
            raise arg_type_error("size", size)

    source = property(
        _close_validated(lambda self: getattr(self, self._source_type.value)),
        doc="""
        Image :term:`source`

        :type: Union[PIL.Image.Image, str]

        GET:
            Returns the :term:`source` from which the instance was initialized.
        """,
    )

    source_type = property(
        lambda self: self._source_type,
        doc="""
        Image :term:`source` type

        :type: ImageSource

        GET:
            Returns the type of :term:`source` from which the instance was initialized.
        """,
    )

    width = property(
        lambda self: self._size if isinstance(self._size, Size) else self._size[0],
        lambda self, width: self.set_size(width),
        doc="""
        Image width

        :type: Union[Size, int]

        GET:
            Returns:

            * The image width (in columns), if the image size is
              :term:`fixed <fixed size>`.
            * A :py:class:`~term_image.image.Size` enum member; if the image size
              is :term:`dynamic <dynamic size>`.

        SET:
            If set to:

            * a positive :py:class:`int`; the image width is set to the given value
              and the height is set proportionally.
            * a :py:class:`~term_image.image.Size` enum member; the image size is set
              as prescibed by the enum member.
            * ``None``; equivalent to :py:attr:`~term_image.image.Size.FIT`.

            This results in a :term:`fixed size`.
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

        * In most cases, it's not necessary to explicitly call this method, as it's
          automatically called when the instance is garbage-collected.
        * This method can be safely called multiple times.
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
        pad_width: int = 0,
        v_align: Optional[str] = None,
        pad_height: int = -2,
        alpha: Optional[float, str] = _ALPHA_THRESHOLD,
        *,
        animate: bool = True,
        repeat: int = -1,
        cached: Union[bool, int] = 100,
        scroll: bool = False,
        check_size: bool = True,
        **style: Any,
    ) -> None:
        """Draws the image to standard output.

        Args:
            h_align: Horizontal alignment ("left" / "<", "center" / "|" or
              "right" / ">"). Default: center.
            pad_width: Number of columns within which to align the image.

              * Excess columns are filled with spaces.
              * Must not be greater than the :term:`terminal width`.

            v_align: Vertical alignment ("top"/"^", "middle"/"-" or "bottom"/"_").
              Default: middle.
            pad_height: Number of lines within which to align the image.

              * Excess lines are filled with spaces.
              * Must not be greater than the :term:`terminal height`,
                **for animations**.

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

            animate: If ``False``, disable animation i.e draw only the current frame of
              an animated image.
            repeat: The number of times to go over all frames of an animated image.
              A negative value implies infinite repetition.
            cached: Determines if :term:`rendered` frames of an animated image will be
              cached (for speed up of subsequent renders of the same frame) or not.

              * If :py:class:`bool`, it directly sets if the frames will be cached or
                not.
              * If :py:class:`int`, caching is enabled only if the framecount of the
                image is less than or equal to the given number.

            scroll: Only applies to non-animations. If ``True``, allows the image's
              :term:`rendered height` to be greater than the :term:`terminal height`.
            check_size: If ``False``, rendered size validation is not performed for
              non-animations. Does not affect padding size validation.
            style: Style-specific render parameters. See each subclass for it's own
              usage.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
            term_image.exceptions.InvalidSizeError: The image's :term:`rendered size`
              can not fit into the :term:`terminal size`.
            term_image.exceptions.StyleError: Unrecognized style-specific render
              parameter(s).
            term_image.exceptions.RenderError: An error occurred during
              :term:`rendering`.

        * If *pad_width* or *pad_height* is:

          * positive, it is **absolute** and used as-is.
          * non-positive, it is **relative** to the corresponding terminal dimension
            (**at the point of calling this method**) and equivalent to the absolute
            dimension ``max(terminal_dimension + frame_dimension, 1)``.

        * :term:`padding width` is always validated.
        * *animate*, *repeat* and *cached* apply to :term:`animated` images only.
          They are simply ignored for non-animated images.
        * For animations (i.e animated images with *animate* set to ``True``):

          * *scroll* is ignored.
          * Image size is always validated, if set.
          * :term:`Padding height` is always validated.

        * Animations, **by default**, are infinitely looped and can be terminated
          with :py:data:`~signal.SIGINT` (``CTRL + C``), **without** raising
          :py:class:`KeyboardInterrupt`.
        """
        fmt = self._check_formatting(h_align, pad_width, v_align, pad_height)

        if alpha is not None:
            if isinstance(alpha, float):
                if not 0.0 <= alpha < 1.0:
                    raise arg_value_error_range("alpha", alpha)
            elif isinstance(alpha, str):
                if not _ALPHA_BG_FORMAT.fullmatch(alpha):
                    raise arg_value_error_msg("Invalid hex color string", alpha)
            else:
                raise arg_type_error("alpha", alpha)

        if self._is_animated and not isinstance(animate, bool):
            raise arg_type_error("animate", animate)

        terminal_width, terminal_height = get_terminal_size()
        if pad_width > terminal_width:
            raise arg_value_error_range(
                "pad_width", pad_width, got_extra=f"terminal_width={terminal_width}"
            )

        animation = self._is_animated and animate

        if animation and pad_height > terminal_height:
            raise arg_value_error_range(
                "pad_height",
                pad_height,
                got_extra=f"terminal_height={terminal_height}, animation={animation}",
            )

        for arg in ("scroll", "check_size"):
            arg_value = locals()[arg]
            if not isinstance(arg_value, bool):
                raise arg_type_error(arg, arg_value)

        # Checks for *repeat* and *cached* are delegated to `ImageIterator`.

        def render(image: PIL.Image.Image) -> None:
            # Hide the cursor immediately if the output is a terminal device
            sys.stdout.isatty() and print(HIDE_CURSOR, end="", flush=True)
            try:
                style_args = self._check_style_args(style)
                if animation:
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
                print(SGR_NORMAL, SHOW_CURSOR * sys.stdout.isatty(), sep="")

        self._renderer(
            render,
            scroll=scroll,
            check_size=check_size,
            animated=animation,
        )

    @classmethod
    def from_file(
        cls,
        filepath: Union[str, os.PathLike],
        **kwargs: Union[None, int],
    ) -> BaseImage:
        """Creates an instance from an image file.

        Args:
            filepath: Relative/Absolute path to an image file.
            kwargs: Same keyword arguments as the class constructor.

        Returns:
            A new instance.

        Raises:
            TypeError: *filepath* is of an inappropriate type.
            FileNotFoundError: The given path does not exist.
            IsADirectoryError: Propagated from from :py:func:`PIL.Image.open`.
            PIL.UnidentifiedImageError: Propagated from from :py:func:`PIL.Image.open`.

        Also Propagates exceptions raised or propagated by the class constructor.
        """
        if not isinstance(filepath, (str, os.PathLike)):
            raise arg_type_error("filepath", filepath)

        if isinstance(filepath, os.PathLike):
            filepath = filepath.__fspath__()
            if isinstance(filepath, bytes):
                filepath = filepath.decode()

        # Intentionally propagates `IsADirectoryError` since the message is OK
        try:
            img = Image.open(filepath)
        except FileNotFoundError:
            raise FileNotFoundError(f"No such file: {filepath!r}") from None
        except UnidentifiedImageError as e:
            e.args = (f"Could not identify {filepath!r} as an image",)
            raise

        with img:
            new = cls(img, **kwargs)
        # Absolute paths work better with symlinks, as opposed to real paths:
        # less confusing, Filename is as expected, helps in path comparisons
        new._source = os.path.abspath(filepath)
        new._source_type = ImageSource.FILE_PATH
        return new

    @classmethod
    def from_url(
        cls,
        url: str,
        **kwargs: Union[None, int],
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
            PIL.UnidentifiedImageError: Propagated from :py:func:`PIL.Image.open`.

        Also propagates connection-related exceptions from :py:func:`requests.get`
        and exceptions raised or propagated by the class constructor.

        NOTE:
            This method creates a temporary file, but only after successful
            initialization. The file is removed:

            - when :py:meth:`close` is called,
            - upon exiting a ``with`` statement block that uses the instance as a
              context manager, or
            - when the instance is garbage collected.
        """
        if not isinstance(url, str):
            raise arg_type_error("url", url)
        if not all(urlparse(url)[:3]):
            raise arg_value_error_msg("Invalid URL", url)

        # Propagates connection-related errors.
        response = requests.get(url, stream=True)
        if response.status_code == 404:
            raise URLNotFoundError(f"URL {url!r} does not exist.")

        # Ensure initialization is successful before writing to file
        try:
            new = cls(Image.open(io.BytesIO(response.content)), **kwargs)
        except UnidentifiedImageError as e:
            e.args = (f"The URL {url!r} doesn't link to an identifiable image",)
            raise

        fd, filepath = mkstemp("-" + os.path.basename(url), dir=_TEMP_DIR)
        os.write(fd, response.content)
        os.close(fd)

        new._source = filepath
        new._source_type = ImageSource.URL
        new._url = url
        return new

    @classmethod
    @abstractmethod
    def is_supported(cls) -> bool:
        """Checks if the implemented :term:`render style` is supported by the
        :term:`active terminal`.

        Returns:
            ``True`` if the render style implemented by the invoking class is supported
            by the :term:`active terminal`. Otherwise, ``False``.

        ATTENTION:
            Support checks for most (if not all) render styles require :ref:`querying
            <terminal-queries>` the :term:`active terminal` the **first time** they're
            executed.

            Hence, it's advisable to perform all necessary support checks (call
            this method on required style classes) at an early stage of a program,
            before user input is expected. If using automatic style selection,
            calling :py:func:`~term_image.image.auto_image_class` only should be
            sufficient.
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
            raise arg_type_error("pos", pos)
        if not 0 <= pos < self.n_frames:
            raise arg_value_error_range("pos", pos, f"n_frames={self.n_frames}")
        if self._is_animated:
            self._seek_position = pos

    @ClassInstanceMethod
    def set_render_method(cls, method: Optional[str] = None) -> None:
        """Sets the :term:`render method` used by instances of a :term:`render style`
        class that implements multiple render methods.

        Args:
            method: The render method to be set or ``None`` for a reset
              (case-insensitive).

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.

        See the **Render Methods** section in the description of subclasses that
        implement such for their specific usage.

        If *method* is not ``None`` and this method is called via:

        - a class, the class-wide render method is set.
        - an instance, the instance-specific render method is set.

        If *method* is ``None`` and this method is called via:

        - a class, the class-wide render method is unset, so that it uses that of
          its parent style class (if any) or the default.
        - an instance, the instance-specific render method is unset, so that it
          uses the class-wide render method thenceforth.

        Any instance without a render method set uses the class-wide render method.

        NOTE:
            *method* = ``None`` is always allowed, even if the render style doesn't
            implement multiple render methods.

            The **class-wide** render method is :term:`descendant`.
        """
        if method is not None and not isinstance(method, str):
            raise arg_type_error("method", method)
        if method is not None and method.lower() not in cls._render_methods:
            raise ValueError(f"Unknown render method {method!r} for {cls.__name__}")

        if not method:
            if cls._render_methods:
                cls._render_method = cls._default_render_method
        else:
            cls._render_method = method

    @set_render_method.instancemethod
    def set_render_method(self, method: Optional[str] = None) -> None:
        if method is not None and not isinstance(method, str):
            raise arg_type_error("method", method)
        if method is not None and method.lower() not in type(self)._render_methods:
            raise ValueError(
                f"Unknown render method {method!r} for {type(self).__name__}"
            )

        if not method:
            try:
                del self._render_method
            except AttributeError:
                pass
        else:
            self._render_method = method

    def set_size(
        self,
        width: Union[int, Size, None] = None,
        height: Union[int, Size, None] = None,
        frame_size: Tuple[int, int] = (0, -2),
    ) -> None:
        """Sets the image size (with extended control).

        Args:
            width: Can be

              * a positive integer; horizontal dimension of the image, in columns.
              * a :py:class:`~term_image.image.Size` enum member.

            height: Can be

              * a positive integer; vertical dimension of the image, in lines.
              * a :py:class:`~term_image.image.Size` enum member.

            frame_size: :term:`Frame size`, ``(columns, lines)``.
              If *columns* or *lines* is

              * positive, it is **absolute** and used as-is.
              * non-positive, it is **relative** to the corresponding terminal dimension
                and equivalent to the absolute dimension
                ``max(terminal_dimension + frame_dimension, 1)``.

              This is used only when neither *width* nor *height* is an ``int``.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.

        * If both width and height are not ``None``, they must be positive integers
          and :term:`manual sizing` applies i.e the image size is set as given without
          preserving aspect ratio.
        * If *width* or *height* is a :py:class:`~term_image.image.Size` enum
          member, :term:`automatic sizing` applies as prescribed by the enum member.
        * If neither *width* nor *height* is given (or both are ``None``),
          :py:attr:`~term_image.image.Size.FIT` applies.
        """
        width_height = (width, height)
        for arg_name, arg_value in zip(("width", "height"), width_height):
            if not (arg_value is None or isinstance(arg_value, (Size, int))):
                raise arg_type_error(arg_name, arg_value)
            if isinstance(arg_value, int) and arg_value <= 0:
                raise arg_value_error_range(arg_name, arg_value)

        if width is not None is not height:
            if not all(isinstance(x, int) for x in width_height):
                width_type = type(width).__name__
                height_type = type(height).__name__
                raise TypeError(
                    "Both 'width' and 'height' are specified but are not both integers "
                    f"(got: ({width_type}, {height_type}))"
                )

            self._size = width_height
            return

        if not (
            isinstance(frame_size, tuple)
            and all(isinstance(x, int) for x in frame_size)
        ):
            raise arg_type_error("frame_size", frame_size)
        if not len(frame_size) == 2:
            raise arg_value_error("frame_size", frame_size)

        self._size = self._valid_size(width, height, frame_size)

    def tell(self) -> int:
        """Returns the current image frame number.

        :rtype: int
        """
        return self._seek_position if self._is_animated else 0

    # Private Methods

    @classmethod
    def _check_format_spec(
        cls, spec: str
    ) -> Tuple[
        str | None,
        int,
        str | None,
        int,
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
            raise arg_value_error_msg("Invalid format specifier", spec)

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
                h_align,
                int(width) if width else 0,
                v_align,
                int(height) if height else -2,
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
        h_align: str | None = None,
        width: int = 0,
        v_align: str | None = None,
        height: int = -2,
    ) -> Tuple[str | None, int, str | None, int]:
        """Validates and transforms formatting arguments.

        Returns:
            The respective arguments appropriate for ``_format_render()``.
        """
        if not isinstance(h_align, (type(None), str)):
            raise arg_type_error("h_align", h_align)
        if None is not h_align not in set("<|>"):
            align = {"left": "<", "center": "|", "right": ">"}.get(h_align)
            if not align:
                raise arg_value_error("h_align", h_align)
            h_align = align

        if not isinstance(v_align, (type(None), str)):
            raise arg_type_error("v_align", v_align)
        if None is not v_align not in set("^-_"):
            align = {"top": "^", "middle": "-", "bottom": "_"}.get(v_align)
            if not align:
                raise arg_value_error("v_align", v_align)
            v_align = align

        terminal_size = get_terminal_size()

        if not isinstance(width, int):
            raise arg_type_error("pad_width", width)
        width = width if width > 0 else max(terminal_size.columns + width, 1)

        if not isinstance(height, int):
            raise arg_type_error("pad_height", height)
        height = height if height > 0 else max(terminal_size.lines + height, 1)

        return h_align, width, v_align, height

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
                    # less costly than membership tests on every class' __bases__
                    if other_cls is __class__:
                        raise StyleError(
                            f"Unknown style-specific render parameter {name!r} for "
                            f"{cls.__name__!r}"
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
                    raise StyleError(
                        f"Unknown style-specific render parameter {name!r} for "
                        f"{cls.__name__!r}"
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

        Every overriding method should call the overridden method (more on this below).
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

        :py:meth:`_get_style_format_spec` may be used to parse the format spec at each
        level of the call chain.
        """
        if spec:
            raise StyleError(
                f"Invalid style-specific format specifier {original!r} "
                f"for {cls.__name__!r}"
                + (f", detected at {spec!r}" if spec != original else "")
            )
        return {}

    @classmethod
    def _clear_frame(cls) -> bool:
        """Clears an animation frame on-screen.

        Called by :py:meth:`_display_animated` just before drawing a new frame.

        | Only required by styles wherein an image is not overwritten by another image
          e.g some graphics-based styles.
        | The base implementation does nothing and should be overridden only if
          required.

        Returns:
            ``True`` if the frame was cleared. Otherwise, ``False``.
        """
        return False

    def _close_image(self, img: PIL.Image.Image) -> None:
        """Closes the given PIL image instance if it isn't the instance' source."""
        if img is not self._source:
            img.close()

    def _display_animated(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        fmt: Tuple[str | None, int, str | None, int],
        repeat: int,
        cached: Union[bool, int],
        **style_args: Any,
    ) -> None:
        """Displays an animated GIF image in the terminal."""
        lines = max(fmt[-1], self.rendered_height)
        prev_seek_pos = self._seek_position
        duration = self._frame_duration
        image_it = ImageIterator(self, repeat, "", cached)
        image_it._animator = image_it._animate(img, alpha, fmt, style_args)
        cursor_up = CURSOR_UP % (lines - 1)
        cursor_down = CURSOR_DOWN % lines

        try:
            print(next(image_it._animator), end="", flush=True)  # First frame

            # Render next frame during current frame's duration
            start = time.time()
            for frame in image_it._animator:  # Renders next frame
                # Left-over of current frame's duration
                time.sleep(max(0, duration - (time.time() - start)))

                # Clear the current frame, if necessary,
                # move cursor up to the beginning of the first line of the image
                # and print the new current frame.
                self._clear_frame()
                print("\r", cursor_up, frame, sep="", end="", flush=True)

                # Render next frame during current frame's duration
                start = time.time()
        except KeyboardInterrupt:
            self._handle_interrupted_draw()
        except Exception:
            self._handle_interrupted_draw()
            raise
        finally:
            image_it.close()
            self._close_image(img)
            self._seek_position = prev_seek_pos
            # Move the cursor to the last line of the image to prevent "overlaid"
            # output in the terminal
            print(cursor_down, end="")

    def _format_render(
        self,
        render: str,
        h_align: str | None,
        width: int,
        v_align: str | None,
        height: int,
    ) -> str:
        """Pads and aligns a primary :term:`render` output.

        NOTE:
            * All arguments should be passed through ``_check_formatting()`` first.
            * Only **absolute** padding dimensions are expected.
        """
        cols, lines = self.rendered_size

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

        if height > lines:
            if v_align == "^":  # top
                top = 0
                bottom = height - lines
            elif v_align == "_":  # bottom
                top = height - lines
                bottom = 0
            else:  # middle
                top = (height - lines) // 2
                bottom = height - lines - top
            top = f"{' ' * width}\n" * top
            bottom = f"\n{' ' * width}" * bottom
        else:
            top = bottom = ""

        return (
            "".join((top, left, render, right, bottom))
            if width > cols or height > lines
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
              the image size.
            pixel_data: If ``False``, ``None`` is returned for all pixel data.
            round_alpha: Only applies when *alpha* is a ``float``.

              If ``True``, returned alpha values are bi-level (``0`` or ``255``), based
              on the given alpha threshold.
              Also, the image is blended with the active terminal's BG color (or black,
              if undetermined) while leaving the alpha intact.

            frame: If ``True``, implies *img* is being used by :py:class`ImageIterator`,
              hence, *img* is not closed.

        Returns:
            A tuple containing

            * An image appropriately converted, resized and composited (if need be) and
              having mode ``RGB`` or ``RGBA``, depending on the mode of the source
              image.
            * ``rgb``, a list of ``(r, g, b)`` tuples containing the channel values of
              the image's pixels in a flattened row-major order, where ``r``, ``g``,
              ``b`` are integers in the range [0, 255]; OR ``None`` if *pixel_data* is
            * ``a``, a list of integers in the range [0, 255] representing the alpha
              channel values of the image's pixels in a flattened row-major order;
              OR ``None`` if *pixel_data* is ``False``.
        """

        def convert_resize_img(mode: str):
            nonlocal img

            if img.mode != mode:
                prev_img = img
                try:
                    img = img.convert(mode)
                # Possible for images in some modes e.g "La"
                except Exception as e:
                    raise RenderError("Unable to convert image") from e
                finally:
                    if frame_img is not prev_img:
                        self._close_image(prev_img)

            if img.size != size:
                prev_img = img
                try:
                    img = img.resize(size, Image.Resampling.BOX)
                # Highly unlikely since render size can never be zero
                except Exception as e:
                    raise RenderError("Unable to resize image") from e
                finally:
                    if frame_img is not prev_img:
                        self._close_image(prev_img)

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
                if frame_img is not img:
                    self._close_image(img)
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
                    if frame_img is not img:
                        self._close_image(img)
                    img = bg

            if pixel_data:
                rgb = list((img if img.mode == "RGB" else img.convert("RGB")).getdata())

        return (img, *(pixel_data and (rgb, a) or (None, None)))

    @abstractmethod
    def _get_render_size(self) -> Tuple[int, int]:
        """Returns the size (in pixels) required to render the image."""
        raise NotImplementedError

    @classmethod
    def _get_style_format_spec(
        cls, spec: str, original: str
    ) -> Tuple[str, List[Union[None, str, Tuple[Optional[str]]]]]:
        """Parses a style-specific format specifier.

        See :py:meth:`_check_style_format_spec`.

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
            raise StyleError(
                f"Invalid style-specific format specifier {original!r} "
                f"for {cls.__name__!r}, detected at {invalid!r}"
            )

        return parent, fields

    @staticmethod
    def _handle_interrupted_draw():
        """Performs any necessary actions when image drawing is interrupted."""

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
              :py:class:`PIL.Image.Image` instance corresponding to the source.

            args: Positional arguments to pass on to *renderer*, after the
              :py:class:`PIL.Image.Image` instance.
            scroll: See *scroll* in :py:meth:`draw`.
            check_size: See *check_size* in :py:meth:`draw`.
            animated: If ``True``, *scroll* and *check_size* are ignored and the size
              is validated.
            kwargs: Keyword arguments to pass on to *renderer*.

        Returns:
            The return value of *renderer*.

        Raises:
            term_image.exceptions.InvalidSizeError: *check_size* or *animated* is
              ``True`` and the image's :term:`rendered size` can not fit into the
              :term:`terminal size`.
            term_image.exceptions.TermImageError: The image has been finalized.
        """
        _size = self._size
        try:
            if isinstance(_size, Size):
                self.set_size(_size)
            elif check_size or animated:
                terminal_size = get_terminal_size()
                if any(
                    map(
                        gt,
                        # The compared height will be 0 if *scroll* is `True`.
                        # So, the height comparison will always be `False`
                        # since the terminal height should never be < 0.
                        map(mul, self.rendered_size, (1, not scroll)),
                        terminal_size,
                    )
                ):
                    raise InvalidSizeError(
                        "The "
                        + ("animation" if animated else "image")
                        + " cannot fit into the terminal size"
                    )

                # Reaching here means it's either valid or *scroll* is `True`.
                if animated and self.rendered_height > terminal_size.lines:
                    raise InvalidSizeError(
                        "The rendered height is greater than the terminal height for "
                        "an animation"
                    )

            return renderer(self._get_image(), *args, **kwargs)

        finally:
            if isinstance(_size, Size):
                self.size = _size

    def _valid_size(
        self,
        width: Union[int, Size, None] = None,
        height: Union[int, Size, None] = None,
        frame_size: Tuple[int, int] = (0, -2),
    ) -> Tuple[int, int]:
        """Returns an image size tuple.

        See :py:meth:`set_size` for the description of the parameters.
        """
        ori_width, ori_height = self._original_size
        columns, lines = map(
            lambda frame_dim, terminal_dim: (
                frame_dim if frame_dim > 0 else max(terminal_dim + frame_dim, 1)
            ),
            frame_size,
            get_terminal_size(),
        )
        frame_width = self._pixels_cols(cols=columns)
        frame_height = self._pixels_lines(lines=lines)

        # As for cell ratio...
        #
        # Take for example, pixel ratio = 2.0
        # (i.e cell ratio = 1.0; square character cells).
        # To adjust the image to the proper scale, we either reduce the
        # width (i.e divide by 2.0) or increase the height (i.e multiply by 2.0).
        #
        # On the other hand, if the pixel ratio = 0.5
        # (i.e cell ratio = 0.25; vertically oblong character cells).
        # To adjust the image to the proper scale, we either increase the width
        # (i.e divide by the 0.5) or reduce the height (i.e multiply by the 0.5).
        #
        # Therefore, for the height, we always multiply by the pixel ratio
        # and for the width, we always divide by the pixel ratio.
        # The non-constraining axis is always the one directly adjusted.

        if all(not isinstance(x, int) for x in (width, height)):
            if Size.AUTO in (width, height):
                width = height = (
                    Size.FIT
                    if (
                        ori_width > frame_width
                        or round(ori_height * self._pixel_ratio) > frame_height
                    )
                    else Size.ORIGINAL
                )
            elif Size.FIT_TO_WIDTH in (width, height):
                return (
                    self._pixels_cols(pixels=frame_width) or 1,
                    self._pixels_lines(
                        pixels=round(
                            self._width_height_px(w=frame_width) * self._pixel_ratio
                        )
                    )
                    or 1,
                )

            if Size.ORIGINAL in (width, height):
                return (
                    self._pixels_cols(pixels=ori_width) or 1,
                    self._pixels_lines(pixels=round(ori_height * self._pixel_ratio))
                    or 1,
                )

            # The smaller fraction will fit on both axis.
            # Hence, the axis with the smaller ratio is the constraining axis.
            # Constraining by the axis with the larger ratio will cause the image
            # to not fit into the axis with the smaller ratio.
            width_ratio = frame_width / ori_width
            height_ratio = frame_height / ori_height
            smaller_ratio = min(width_ratio, height_ratio)

            # Set the dimension on the constraining axis to exactly its corresponding
            # frame dimension and the dimension on the other axis to the same ratio of
            # its corresponding original image dimension
            _width_px = ori_width * smaller_ratio
            _height_px = ori_height * smaller_ratio

            # The cell ratio should directly affect the non-constraining axis since the
            # constraining axis is already fully occupied at this point
            if height_ratio > width_ratio:
                _height_px = _height_px * self._pixel_ratio
                # If height becomes greater than the max, reduce it to the max
                height_px = min(_height_px, frame_height)
                # Calculate the corresponding width
                width_px = round((height_px / _height_px) * _width_px)
                # Round the height
                height_px = round(height_px)
            else:
                _width_px = _width_px / self._pixel_ratio
                # If width becomes greater than the max, reduce it to the max
                width_px = min(_width_px, frame_width)
                # Calculate the corresponding height
                height_px = round((width_px / _width_px) * _height_px)
                # Round the width
                width_px = round(width_px)
            return (
                self._pixels_cols(pixels=width_px) or 1,
                self._pixels_lines(pixels=height_px) or 1,
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

        return (width or 1, height or 1)

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
    """Base of all :ref:`graphics-based`.

    Raises:
        term_image.exceptions.StyleError: The :term:`active terminal` doesn't support
          the render style.

    See :py:class:`BaseImage` for the description of the constructor.

    ATTENTION:
        This class cannot be directly instantiated. Image instances should be created
        from its subclasses.

    TIP:
        To allow instantiation regardless of whether the render style is supported or
        not, enable :py:attr:`~term_image.image.BaseImage.forced_support`.
    """

    # Size unit conversion already involves cell size calculation
    _pixel_ratio: float = 1.0

    def __new__(
        cls,
        image: PIL.Image.Image,
        *,
        width: Union[int, Size, None] = None,
        height: Union[int, Size, None] = None,
    ) -> None:
        # calls `is_supported()` first to set required class attributes, in case
        # support is forced for a style that is actually supported
        if not (cls.is_supported() or cls._forced_support):
            raise StyleError(
                f"{cls.__name__!r} is not supported in the active terminal"
            )
        return super().__new__(cls)

    def _get_minimal_render_size(self, *, adjust: bool = False) -> Tuple[int, int]:
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
    """Base of all :ref:`text-based`.

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

    # 240 colors i.e excluding the first 16
    _XTERM_240_PALETTE_IMAGE = Image.new("P", (1, 1))
    _XTERM_240_PALETTE_IMAGE.putpalette(XTERM_256_PALETTE[16 * 3 :])

    # Pixels are represented in a 1-to-2 ratio within one character cell
    # pixel-size == width * height/2
    # pixel-ratio == width / (height/2) == 2 * (width / height) == 2 * cell-ratio
    _pixel_ratio = property(lambda _: get_cell_ratio() * 2)

    @staticmethod
    @cached
    def _is_on_kitty() -> bool:
        return get_terminal_name_version()[0] == "kitty"

    def _get_render_data(
        self,
        img: PIL.Image.Image,
        *args,
        frame: bool = False,
        indexed_color: bool = False,
        **kwargs,
    ) -> tuple[
        PIL.Image.Image,
        list[tuple[int, int, int]] | list[int] | None,
        list[int] | None,
    ]:
        """
        See :py:meth:`BaseImage._render_image` for the description of the method and
        all other parameters not described here.

        Args:
            indexed_color: Whether to quantize the render image to a 240-color palette.

        Returns:
            The same as the overriden method if *indexed_color* is ``False``. Otherwise,

            * The returned image has mode ``P`` or ``PA``, depending on the mode of the
              source image.
            * ``rgb`` is a list of integers in the range [0, 255], where each integer
              is a valid index for a 256-color terminal palette.
        """
        if indexed_color:
            frame_img = img if frame else None
        img, rgb, a = super()._get_render_data(img, *args, frame=frame, **kwargs)

        if indexed_color:
            orig_img = img

            img = img.copy() if img.mode == "RGB" else img.convert("RGB")
            with img:
                quantized_img = img.quantize(
                    palette=__class__._XTERM_240_PALETTE_IMAGE, dither=Image.Dither.NONE
                )

            if orig_img.mode == "RGBA":
                with quantized_img:
                    quantized_img = quantized_img.convert("PA")
                quantized_img.putalpha(orig_img.getchannel("A"))

            if frame_img is not orig_img:
                self._close_image(orig_img)

            img = quantized_img
            rgb = [index + 16 for index in img.getdata(0)]

        return (img, rgb, a)

    @abstractmethod
    def _render_image(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        frame: bool = False,
        split_cells: bool = False,  # For internal use only
    ) -> str:
        """
        See :py:meth:`BaseImage._render_image` for the description of the method and
        all other parameters not described here.

        Args:
            split_cells: If ``True``, the cells of the image are separated by a
              ``NULL`` ("\\0").

              - must be defined and implemented by every text-based style
                (i.e subclasses of this class).
              - required by some other parts of the library.
              - only used internally, across the library.
        """
        raise NotImplementedError


class ImageIterator:
    """Efficiently iterate over :term:`rendered` frames of an :term:`animated` image

    Args:
        image: Animated image.
        repeat: The number of times to go over the entire image. A negative value
          implies infinite repetition.
        format_spec: The :ref:`format specifier <format-spec>` for the rendered
          frames (default: auto).
        cached: Determines if the :term:`rendered` frames will be cached (for speed up
          of subsequent renders) or not. If it is

          * a boolean, caching is enabled if ``True``. Otherwise, caching is disabled.
          * a positive integer, caching is enabled only if the framecount of the image
            is less than or equal to the given number.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.
        term_image.exceptions.StyleError: Invalid style-specific format specifier.

    * If *repeat* equals ``1``, caching is disabled.
    * The iterator has immediate response to changes in the image size.
    * If the image size is :term:`dynamic <dynamic size>`, it's computed per frame.
    * The number of the last yielded frame is set as the image's seek position.
    * Directly adjusting the seek position of the image doesn't affect iteration.
      Use :py:meth:`ImageIterator.seek` instead.
    * After the iterator is exhausted, the underlying image is set to frame ``0``.
    """

    def __init__(
        self,
        image: BaseImage,
        repeat: int = -1,
        format_spec: str = "",
        cached: Union[bool, int] = 100,
    ) -> None:
        if not isinstance(image, BaseImage):
            raise arg_type_error("image", image)
        if not image._is_animated:
            raise ValueError("'image' is not animated")

        if not isinstance(repeat, int):
            raise arg_type_error("repeat", repeat)
        if not repeat:
            raise arg_value_error("repeat", repeat)

        if not isinstance(format_spec, str):
            raise arg_type_error("format_spec", format_spec)
        *fmt, alpha, style_args = image._check_format_spec(format_spec)

        if not isinstance(cached, int):  # `bool` is a subclass of `int`
            raise arg_type_error("cached", cached)
        if False is not cached <= 0:
            raise arg_value_error_range("cached", cached)

        self._image = image
        self._repeat = repeat
        self._format = format_spec
        self._cached = repeat != 1 and (
            cached if isinstance(cached, bool) else image.n_frames <= cached
        )
        self._loop_no = None
        self._animator = image._renderer(
            self._animate, alpha, fmt, style_args, check_size=False
        )

    def __del__(self) -> None:
        self.close()

    def __iter__(self) -> ImageIterator:
        return self

    def __next__(self) -> str:
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

    def __repr__(self) -> str:
        return (
            "{}(image={!r}, repeat={}, format_spec={!r}, cached={}, loop_no={})".format(
                type(self).__name__,
                *self.__dict__.values(),
            )
        )

    loop_no = property(
        lambda self: self._loop_no,
        doc="""Iteration repeat countdown

        :type: Optional[int]

        GET:
            Returns:

            * ``None``, if iteration hasn't started.
            * Otherwise, the current iteration repeat countdown value.

        Changes on the first iteration of each loop, except for infinite iteration
        where it's always ``-1``. When iteration has ended, the value is zero.
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
            self._image._close_image(self._img)
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
            term_image.exceptions.TermImageError: Iteration has not yet started or the
              iterator is exhausted/closed.

        Frame numbers start from ``0`` (zero).
        """
        if not isinstance(pos, int):
            raise arg_type_error("pos", pos)
        if not 0 <= pos < self._image.n_frames:
            raise arg_value_error_range("pos", pos, f"n_frames={self._image.n_frames}")

        try:
            self._animator.send(pos)
        except TypeError:
            raise TermImageError("Iteration has not yet started") from None
        except AttributeError:
            raise TermImageError("Iterator exhausted or closed") from None

    def _animate(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        fmt: Tuple[Union[None, str, int]],
        style_args: Dict[str, Any],
    ) -> Generator[str, int, None]:
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
                        cache[n] = (frame, hash(image.rendered_size))

            sent = yield frame
            n = n + 1 if sent is None else sent - 1

        if cached:
            n_frames = len(cache)
        while repeat:
            while n < n_frames:
                if sent is None:
                    image._seek_position = n
                    frame, size_hash = cache[n]
                    if hash(image.rendered_size) != size_hash:
                        frame = image._format_render(
                            image._render_image(img, alpha, frame=True, **style_args),
                            *fmt,
                        )
                        cache[n] = (frame, hash(image.rendered_size))

                sent = yield frame
                n = n + 1 if sent is None else sent - 1

            image._seek_position = n = 0
            if repeat > 0:  # Avoid infinitely large negative numbers
                self._loop_no = repeat = repeat - 1

        # For consistency in behaviour
        if img is image._source:
            img.seek(0)


@atexit.register
def _cleanup_temp_dir():
    rmtree(_TEMP_DIR, ignore_errors=True)
