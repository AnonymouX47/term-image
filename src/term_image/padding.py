"""
.. The Padding API
"""

from __future__ import annotations

__all__ = (
    "Padding",
    "AlignedPadding",
    "ExactPadding",
    "HAlign",
    "VAlign",
    "PaddingError",
    "RelativePaddingDimensionError",
)

import os
from abc import ABCMeta, abstractmethod
from dataclasses import astuple, dataclass
from enum import IntEnum, auto

from typing_extensions import override

from .ctlseqs import cursor_forward
from .exceptions import TermImageError
from .geometry import RawSize, Size
from .utils import arg_value_error_range

# Variables ====================================================================


_ALIGN_RATIOS = ((0, 1), (1, 2), (1, 1))
"""Ratios of *left* and *top* exact padding dimensions for aligned padding.

::

   dim = (padded_dim - render_dim) * RATIOS[i][0] // RATIOS[i][1]

where ``i`` = ``{h|v}_align``.
"""


# Enumerations =================================================================


class HAlign(IntEnum):
    """Horizontal alignment enumeration"""

    LEFT = 0
    """Left horizontal alignment

    :meta hide-value:
    """

    CENTER = auto()
    """Center horizontal alignment

    :meta hide-value:
    """

    RIGHT = auto()
    """Right horizontal alignment

    :meta hide-value:
    """


class VAlign(IntEnum):
    """Vertical alignment enumeration"""

    TOP = 0
    """Top vertical alignment

    :meta hide-value:
    """

    MIDDLE = auto()
    """Middle vertical alignment

    :meta hide-value:
    """

    BOTTOM = auto()
    """Bottom vertical alignment

    :meta hide-value:
    """


# Classes ======================================================================


class Padding(metaclass=ABCMeta):
    """:term:`Render output` padding.

    Args:
        fill: Determines the string with which render outputs will be padded.

          May be any string that occupies exactly **one column** on a terminal screen,
          or an empty string. If empty, the padding simply advances the cursor without
          overwriting existing content on the terminal screen.

    ATTENTION:
        This is an abstract base class. Hence, only **concrete** subclasses can be
        instantiated.

    .. seealso::

       :ref:`padding-ext-api`
          :py:class:`Padding`\\ 's Extension API
    """

    # Class Attributes =========================================================

    __slots__ = ("fill",)

    # Instance Attributes ======================================================

    fill: str
    """Fill string"""

    # Special Methods ==========================================================

    def __init__(self, fill: str = " ") -> None:
        # Subclasses are to be "immutable", `super()` is costlier
        __class__.__setattr__(self, "fill", fill)  # type: ignore[name-defined]

    # Public Methods ===========================================================

    def get_padded_size(self, render_size: Size) -> Size:
        """Computes an expected padded :term:`render size`.

        Args:
            render_size: Render size.

        Returns:
            The size of the :term:`render output` that would be produced by using
            this instance to pad a render output **with the given size**.
        """
        left, top, right, bottom = self._get_exact_dimensions_(render_size)
        width, height = render_size

        return Size(left + width + right, top + height + bottom)

    def pad(self, render: str, render_size: Size) -> str:
        """Pads a :term:`render output`.

        Args:
            render: A render output, in the form specified to be returned by
              :py:meth:`Renderable._render_()
              <term_image.renderable.Renderable._render_>`.
            render_size: :term:`Render size` of *render*.

        Returns:
            The padded render output.

            This is also in the form specified to be returned by
            :py:meth:`Renderable._render_()
            <term_image.renderable.Renderable._render_>`, provided *render* is.
        """
        left, top, right, bottom = self._get_exact_dimensions_(render_size)
        width = left + render_size.width + right
        horizontal = left or right
        vertical = top or bottom
        fill = self.fill

        if fill:
            left_padding = fill * left
            right_padding = fill * right
            top_padding = f"{fill * width}\n" * top if top else ""
            bottom_padding = f"\n{fill * width}" * bottom if bottom else ""
        else:
            left_padding = cursor_forward(left)
            right_padding = cursor_forward(right)
            top_padding = f"{cursor_forward(width)}\n" * top if top else ""
            bottom_padding = f"\n{cursor_forward(width)}" * bottom if bottom else ""

        return (
            "".join(
                (
                    top_padding,
                    left_padding,
                    (
                        render.replace("\n", f"{right_padding}\n{left_padding}")
                        if horizontal
                        else render
                    ),
                    right_padding,
                    bottom_padding,
                )
            )
            if horizontal or vertical
            else render
        )

    def to_exact(self, render_size: Size) -> ExactPadding:
        """Converts the padding to an exact padding for the given :term:`render size`.

        Args:
            render_size: :term:`Render size`.

        Returns:
            An equivalent exact padding, **with respect to the given render size**
            i.e one that would produce the same result as the padding being converted,
            **for the given render size**.

        This is useful to avoid recomputing the exact padding dimensions for **the
        same render size**.
        """
        return (
            self
            if isinstance(self, ExactPadding)
            else ExactPadding(*self._get_exact_dimensions_(render_size), self.fill)
        )

    # Extension methods ========================================================

    @abstractmethod
    def _get_exact_dimensions_(self, render_size: Size) -> tuple[int, int, int, int]:
        """Returns the exact padding dimensions for the given :term:`render size`.

        Args:
            render_size: :term:`Render size`.

        Returns:
            Returns the exact padding dimensions, ``(left, top, right, bottom)``.

        This is called to implement operations in the public API.
        """
        raise NotImplementedError


@dataclass(frozen=True)
class AlignedPadding(Padding):
    """Aligned :term:`render output` padding.

    Args:
        width: Minimum :term:`render width`.
        height: Minimum :term:`render height`.
        h_align: Horizontal alignment.
        v_align: Vertical alignment.

    If *width* or *height* is:

    * positive, it is **absolute** and used as-is.
    * non-positive, it is **relative** to the corresponding terminal dimension
      (**at the point of resolution**) and equivalent to the absolute dimension
      ``max(terminal_dimension + relative_dimension, 1)``.

    The *padded render dimension* (i.e the dimension of a :term:`render output` after
    it's padded) on each axis is given by::

       padded_dimension = max(render_dimension, absolute_minimum_dimension)

    In words... If the **absolute** *minimum render dimension* on an axis is less than
    or equal to the corresponding *render dimension*, there is no padding on that axis
    and the *padded render dimension* on that axis is equal to the *render dimension*.
    Otherwise, the render output will be padded along that axis and the *padded render
    dimension* on that axis is equal to the *minimum render dimension*.

    The amount of padding to each side depends on the alignment, defined by *h_align*
    and *v_align*.

    IMPORTANT:
        :py:class:`RelativePaddingDimensionError` is raised if any padding-related
        computation/operation (basically, calling any method other than
        :py:meth:`resolve`) is performed on an instance with **relative** *minimum
        render dimension(s)* i.e if :py:attr:`relative` is ``True``.

    NOTE:
        Any interface receiving an instance with **relative** dimension(s) should
        typically resolve it/them upon reception.

    TIP:
        * Instances are immutable and hashable.
        * Instances with equal fields compare equal.
    """

    # Class Attributes =========================================================

    __slots__ = ("width", "height", "h_align", "v_align", "relative")

    # Instance Attributes ======================================================

    width: int
    """Minimum :term:`render width`"""

    height: int
    """Minimum :term:`render height`"""

    h_align: HAlign
    """Horizontal alignment"""

    v_align: VAlign
    """Vertical alignment"""

    fill: str

    relative: bool
    """``True`` if either or both *minimum render dimension(s)* is/are relative i.e
    non-positive. Otherwise, ``False``.
    """

    # Special Methods ==========================================================

    def __init__(
        self,
        width: int,
        height: int,
        h_align: HAlign = HAlign.CENTER,
        v_align: VAlign = VAlign.MIDDLE,
        fill: str = " ",
    ):
        super().__init__(fill)

        _setattr = super().__setattr__
        _setattr("width", width)
        _setattr("height", height)
        _setattr("h_align", h_align)
        _setattr("v_align", v_align)
        _setattr("relative", not width > 0 < height)

    def __repr__(self) -> str:
        return "{}(width={}, height={}, h_align={}, v_align={}, fill={!r})".format(
            type(self).__name__,
            self.width,
            self.height,
            self.h_align.name,
            self.v_align.name,
            self.fill,
        )

    # Properties ===============================================================

    @property
    def size(self) -> RawSize:
        """Minimum :term:`render size`

        GET:
            Returns the *minimum render dimensions*.
        """
        return RawSize(self.width, self.height)

    # Public Methods ===========================================================

    @override
    def get_padded_size(self, render_size: Size) -> Size:
        """Computes an expected padded :term:`render size`.

        See :py:meth:`Padding.get_padded_size`.

        Raises:
            RelativePaddingDimensionError: Relative *minimum render dimension(s)*.
        """
        if self.relative:
            raise RelativePaddingDimensionError("Relative minimum render dimension(s)")

        return Size(max(self.width, render_size[0]), max(self.height, render_size[1]))

    def resolve(self, terminal_size: os.terminal_size) -> AlignedPadding:
        """Resolves **relative** *minimum render dimensions*.

        Args:
            terminal_size: The terminal size against which to resolve relative
              dimensions.

        Returns:
            An instance with equivalent **absolute** dimensions.
        """
        if not self.relative:
            return self

        width, height, *args, _ = astuple(self)
        terminal_width, terminal_height = terminal_size
        if width <= 0:
            width = max(terminal_width + width, 1)
        if height <= 0:
            height = max(terminal_height + height, 1)

        return type(self)(width, height, *args)

    # Extension methods ========================================================

    @override
    def _get_exact_dimensions_(self, render_size: Size) -> tuple[int, int, int, int]:
        if self.relative:
            raise RelativePaddingDimensionError("Relative minimum render dimension(s)")

        width, height, h_align, v_align = astuple(self)[:4]
        render_width, render_height = render_size

        if width > render_width:
            padding_width = width - render_width
            numerator, denominator = _ALIGN_RATIOS[h_align]
            left = padding_width * numerator // denominator
            right = padding_width - left
        else:
            left = right = 0

        if height > render_height:
            padding_height = height - render_height
            numerator, denominator = _ALIGN_RATIOS[v_align]
            top = padding_height * numerator // denominator
            bottom = padding_height - top
        else:
            top = bottom = 0

        return left, top, right, bottom


@dataclass(frozen=True)
class ExactPadding(Padding):
    """Exact :term:`render output` padding.

    Args:
        left: Left padding dimension
        top: Top padding dimension.
        right: Right padding dimension
        bottom: Bottom padding dimension

    Raises:
        ValueError: A dimension is negative.

    Pads a render output on each side by the specified amount of lines or columns.

    TIP:
        * Instances are immutable and hashable.
        * Instances with equal fields compare equal.
    """

    # Class Attributes =========================================================

    __slots__ = ("left", "top", "right", "bottom")

    # Instance Attributes ======================================================

    left: int
    """Left padding dimension"""

    top: int
    """Top padding dimension"""

    right: int
    """Right padding dimension"""

    bottom: int
    """Bottom padding dimension"""

    fill: str

    # Special Methods ==========================================================

    def __init__(
        self,
        left: int = 0,
        top: int = 0,
        right: int = 0,
        bottom: int = 0,
        fill: str = " ",
    ) -> None:
        super().__init__(fill)

        _setattr = super().__setattr__
        for name in ("left", "top", "right", "bottom"):
            value = locals()[name]
            if value < 0:
                raise arg_value_error_range(name, value)
            _setattr(name, value)

    # Properties ===============================================================

    @property
    def dimensions(self) -> tuple[int, int, int, int]:
        """Padding dimensions

        GET:
            Returns the padding dimensions, ``(left, top, right, bottom)``.
        """
        return astuple(self)[:4]  # type: ignore[return-value]

    # Extension methods ========================================================

    @override
    def _get_exact_dimensions_(self, render_size: Size) -> tuple[int, int, int, int]:
        return astuple(self)[:4]  # type: ignore[return-value]


# Exceptions ===================================================================


class PaddingError(TermImageError):
    """Base exception class for padding errors."""


class RelativePaddingDimensionError(PaddingError):
    """Raised when a padding operation is performed on an :py:class:`AlignedPadding`
    instance with **relative** minimum render dimension(s).
    """
