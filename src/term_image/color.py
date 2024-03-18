"""
.. The Color API
"""

from __future__ import annotations

__all__ = ("Color",)

import re

from typing_extensions import NamedTuple, Self

from .utils import arg_value_error_range

# Unfortunately, `re` doesn't support repeated capturing groups; only the last match
# is captured. So, we'd have to repeat manually.
# Allows mixture of letter case to simplify parsing.
XX = "[0-9a-f]{2}"
_RGBA_HEX_RE = re.compile(rf"#?({XX})({XX})({XX})({XX})?", re.A | re.I)
del XX


# To bypass `NamedTuple`'s `__new__()` override limitation
class _DummyColor(NamedTuple):
    r: int
    g: int
    b: int
    a: int = 255


class Color(_DummyColor):
    """A color.

    Args:
        r: The red channel.
        g: The green channel.
        b: The blue channel.
        a: The alpha channel (opacity).

    Raises:
        ValueError: The value of a channel is not within the valid range.

    NOTE:
        The valid value range for all channels is 0 to 255, both inclusive.

    TIP:
        This class is a :py:class:`~typing.NamedTuple` of four fields.

    WARNING:
        In the case of multiple inheritance i.e if subclassing this class along with
        other classes, this class should appear last (i.e to the far right) in the
        base class list.
    """

    __slots__ = ()

    # Overrides these descriptors in order to speed up attribute resolution and to
    # simplify auto documentation.
    r: int = _DummyColor.r
    r.__doc__ = """The red channel"""

    g: int = _DummyColor.g
    g.__doc__ = """The green channel"""

    b: int = _DummyColor.b
    b.__doc__ = """The blue channel"""

    a: int = _DummyColor.a
    a.__doc__ = """The alpha channel (opacity)"""

    def __new__(cls, r: int, g: int, b: int, a: int = 255) -> Self:
        # Only the 8 LSb may be set for any value within the range [0, 255].
        # `x & ~255` unsets the 8 LSb. Hence, if the result is non-zero (i.e any
        # of the bits above the lowest 8 is set), it implies `x` is out of range.
        #
        # Actually benchmarked *this* against the "simpler" logically-negated chained
        # comparison (i.e `0 <= x <= 255`) and *this* was significantly faster for all
        # cases i.e within, on the boundaries, and outside (on both sides).
        if (r | g | b | a) & ~255:  # First test to see if *any* is out of range
            if r & ~255:
                raise arg_value_error_range("r", r)
            if g & ~255:
                raise arg_value_error_range("g", g)
            if b & ~255:
                raise arg_value_error_range("b", b)
            if a & ~255:
                raise arg_value_error_range("a", a)

        # Using `tuple` directly instead of `super()` for performance
        return tuple.__new__(cls, (r, g, b, a))

    @property
    def hex(self) -> str:
        """Converts the color to its RGBA hexadecimal representation.

        Returns:
            The RGBA hex color string, starting with the ``#`` character i.e
            ``#rrggbbaa``.

            Each channel is represented by two **lowercase** hex digits ranging from
            ``00`` to ``ff``.
        """
        return "#%02x%02x%02x%02x" % self

    @property
    def rgb(self) -> tuple[int, int, int]:
        """Extracts the R, G and B channels of the color.

        Returns:
            A 3-tuple containing the red, green and blue channel values.
        """
        return self[:3]

    @property
    def rgb_hex(self) -> str:
        """Converts the color to its RGB hexadecimal representation.

        Returns:
            The RGB hex color string, starting with the ``#`` character i.e ``#rrggbb``.

            Each channel is represented by two **lowercase** hex digits ranging from
            ``00`` to ``ff``.
        """
        return "#%02x%02x%02x" % self[:3]

    @classmethod
    def from_hex(cls, color: str) -> Self:
        """Creates a new instance from a hexadecimal color string.

        Args:
            color: A **case-insensitive** RGB or RGBA hex color string, **optionally**
              starting with the ``#`` (pound) character i.e ``[#]rrggbb[aa]``.

        Returns:
            A new instance representing the given hex color string.

        Raises:
            ValueError: Invalid hex color string.

        NOTE:
            For an RGB hex color string, the value of A (the alpha channel) is
            taken to be 255.
        """
        if not (match := _RGBA_HEX_RE.fullmatch(color)):
            raise ValueError(f"Invalid hex color string (got: {color!r})")

        return tuple.__new__(cls, [int(x, 16) for x in match.groups("ff")])

    @classmethod
    def _new(cls, r: int, g: int, b: int, a: int = 255) -> Self:
        """Alternate constructor for internal use only."""
        return tuple.__new__(cls, (r, g, b, a))


_Color = Color._new
