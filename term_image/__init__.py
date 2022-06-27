"""
term-image

Display images in the terminal

Provides
========
    1. A library with features to display images in a terminal in various ways.
    2. A CLI to display images from a local filesystem or URLs.
    3. A TUI to browse through images and directories on a local filesystem
       or from URLS.

It basically works by converting images into text, since that's all conventional
terminals can represent.
Colored output is achieved using ANSI 24-bit color escape codes.

AUTHOR: AnonymouX47 <anonymoux47@gmail.com>
Copyright (c) 2022
"""

from __future__ import annotations

__all__ = ("set_font_ratio", "get_font_ratio", "FontRatio", "TermImageWarning")
__author__ = "AnonymouX47"

from enum import Enum, auto
from operator import truediv
from typing import Union

from .exceptions import TermImageError
from .utils import get_cell_size

version_info = (0, 4, 0)
__version__ = ".".join(map(str, version_info))


def get_font_ratio() -> float:
    """Returns the global :term:`font ratio`.

    See :py:func:`set_font_ratio`.
    """
    # `(1, 2)` is a fallback in case the terminal doesn't respond in time
    return _font_ratio or truediv(*(get_cell_size() or (1, 2)))


def set_font_ratio(ratio: Union[float, FontRatio]) -> None:
    """Sets the global :term:`font ratio`.

    Args:
        ratio: Can be one of the following values.

          * A positive ``float``: a fixed aspect ratio of a character cell in the
            terminal emulator.
          * :py:attr:`FontRatio.AUTO`: the ratio is immediately determined from the
            :term:`active terminal`.
          * :py:attr:`FontRatio.FULL_AUTO`: the ratio is determined from the
            :term:`active terminal` whenever :py:func:`get_font_ratio` is called,
            though with some caching involved, such that the ratio is re-determined
            only if the terminal size changes.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.
        term_image.exceptions.TermImageError: Auto font ratio is not supported
          in the :term:`active terminal` or on the current platform.

    This value is taken into consideration when setting image sizes for **text-based**
    render styles, in order to preserve the aspect ratio of images drawn to the
    terminal.

    NOTE:
        Changing the font ratio does not automatically affect any image that already
        has it's size set. For a change in font ratio to have any effect, the image's
        size has to be set again.

    ATTENTION:
        See :ref:`auto-font-ratio` for details about the auto modes.
    """
    global _auto_font_ratio, _font_ratio

    if isinstance(ratio, FontRatio):
        if _auto_font_ratio is None:
            _auto_font_ratio = get_cell_size() is not None

        if not _auto_font_ratio:
            raise TermImageError(
                "Auto font ratio is not supported in the active terminal or on the "
                "current platform"
            )
        elif ratio is FontRatio.AUTO:
            # `(1, 2)` is a fallback in case the terminal doesn't respond in time
            _font_ratio = truediv(*(get_cell_size() or (1, 2)))
        else:
            _font_ratio = None
    elif isinstance(ratio, float):
        if ratio <= 0.0:
            raise ValueError(f"'ratio' must be greater than zero (got: {ratio})")
        _font_ratio = ratio
    else:
        raise TypeError(
            f"'ratio' must be a float or FontRatio enum (got: {type(ratio).__name__})"
        )


class FontRatio(Enum):
    """Constants for auto font ratio modes"""

    AUTO = auto()
    FULL_AUTO = auto()


class TermImageWarning(UserWarning):
    """Package-specific warning category"""


_font_ratio = 0.5
_auto_font_ratio = None
