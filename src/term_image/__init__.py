"""
term-image

Display images in the terminal

Provides
========
    1. A library with features to display images in a terminal in various ways.
    2. A CLI to display images from a local filesystem or URLs.
    3. A TUI to browse through images and directories on a local filesystem
       or from URLS.

AUTHOR: AnonymouX47 <anonymoux47@gmail.com>
Copyright (c) 2022
"""

from __future__ import annotations

__all__ = ("set_cell_ratio", "get_cell_ratio", "AutoCellRatio")
__author__ = "AnonymouX47"

from enum import Enum, auto
from operator import truediv
from typing import Optional, Union

from .exceptions import TermImageError
from .utils import get_cell_size

version_info = (0, 5, 0)
__version__ = ".".join(map(str, version_info))


def get_cell_ratio() -> float:
    """Returns the global :term:`cell ratio`.

    See :py:func:`set_cell_ratio`.
    """
    # `(1, 2)` is a fallback in case the terminal doesn't respond in time
    return _cell_ratio or truediv(*(get_cell_size() or (1, 2)))


def set_cell_ratio(ratio: Union[float, AutoCellRatio]) -> None:
    """Sets the global :term:`cell ratio`.

    Args:
        ratio: Can be one of the following values.

          * A positive ``float`` value.
          * :py:attr:`AutoCellRatio.FIXED`, the ratio is immediately determined from
            the :term:`active terminal`.
          * :py:attr:`AutoCellRatio.DYNAMIC`, the ratio is determined from the
            :term:`active terminal` whenever :py:func:`get_cell_ratio` is called,
            though with some caching involved, such that the ratio is re-determined
            only if the terminal size changes.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.
        term_image.exceptions.TermImageError: Auto cell ratio is not supported
          in the :term:`active terminal` or on the current platform.

    This value is taken into consideration when setting image sizes for **text-based**
    render styles, in order to preserve the aspect ratio of images drawn to the
    terminal.

    NOTE:
        Changing the cell ratio does not automatically affect any image that has a
        :term:`fixed size`. For a change in cell ratio to take effect, the image's
        size has to be re-set.

    ATTENTION:
        See :ref:`auto-cell-ratio` for details about the auto modes.
    """
    global _cell_ratio

    if isinstance(ratio, AutoCellRatio):
        if AutoCellRatio.is_supported is None:
            AutoCellRatio.is_supported = get_cell_size() is not None

        if not AutoCellRatio.is_supported:
            raise TermImageError(
                "Auto cell ratio is not supported in the active terminal or on the "
                "current platform"
            )
        elif ratio is AutoCellRatio.FIXED:
            # `(1, 2)` is a fallback in case the terminal doesn't respond in time
            _cell_ratio = truediv(*(get_cell_size() or (1, 2)))
        else:
            _cell_ratio = None
    elif isinstance(ratio, float):
        if ratio <= 0.0:
            raise ValueError(f"'ratio' must be greater than zero (got: {ratio})")
        _cell_ratio = ratio
    else:
        raise TypeError(
            "'ratio' must be a float or AutoCellRatio enum member "
            f"(got: {type(ratio).__name__})"
        )


class AutoCellRatio(Enum):
    """Values for setting :ref:`auto-cell-ratio`."""

    is_supported: Optional[bool]

    FIXED = auto()
    DYNAMIC = auto()


_cell_ratio = 0.5
AutoCellRatio.is_supported = None
