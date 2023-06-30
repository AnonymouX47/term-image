"""
.. The Geometry API
"""

from __future__ import annotations

__all__ = ("Size",)

from .utils import arg_type_error


class Size(tuple):
    """The dimensions of a rectangular region.

    Args:
        width: The horizontal dimension
        height: The vertical dimension

    Raises:
        TypeError: An argument is of an inappropriate type.

    NOTE:
        * The meaning of a negative dimension is determined by the recieving interface.
        * This is a subclass of :py:class:`tuple`. Hence, instances can be used anyway
          and anywhere tuples can.
    """

    def __new__(cls, width: int, height: int):
        if not isinstance(width, int):
            raise arg_type_error("width", width)
        if not isinstance(height, int):
            raise arg_type_error("height", height)

        return super().__new__(cls, (width, height))

    width = property(lambda self: self[0], "The horizontal dimension")
    height = property(lambda self: self[1], "The vertical dimension")

    def __repr__(self):
        return f"{type(self).__name__}{super().__repr__()}"
