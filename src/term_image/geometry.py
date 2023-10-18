"""
.. The Geometry API
"""

from __future__ import annotations

__all__ = ("RawSize", "Size")

from typing import NamedTuple

from .utils import arg_value_error_range


class RawSize(NamedTuple):
    """The dimensions of a rectangular region.

    Args:
        width: The horizontal dimension
        height: The vertical dimension

    NOTE:
        * A dimension may be non-positive but the validity and meaning would be
          determined by the receiving interface.
        * This is a subclass of :py:class:`tuple`. Hence, instances can be used anyway
          and anywhere tuples can.
    """

    width: int
    height: int


RawSize.width.__doc__ = "The horizontal dimension"
RawSize.height.__doc__ = "The vertical dimension"


class Size(RawSize):
    """The dimensions of a rectangular region.

    Raises:
        ValueError: Either dimension is non-positive.

    Same as :py:class:`RawSize`, except that both dimensions must be **positive**.
    """

    def __new__(cls, width: int, height: int):
        if width < 1:
            raise arg_value_error_range("width", width)
        if height < 1:
            raise arg_value_error_range("height", height)

        # Using `tuple` directly instead of `super()` for performance
        return tuple.__new__(cls, (width, height))  # type: ignore
