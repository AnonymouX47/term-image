"""
term-image

Display images in the terminal

Copyright (c) 2022, Toluwaleke Ogundipe <anonymoux47@gmail.com>
"""

from __future__ import annotations

__all__ = (
    "DEFAULT_QUERY_TIMEOUT",
    "AutoCellRatio",
    "disable_queries",
    "disable_win_size_swap",
    "enable_queries",
    "enable_win_size_swap",
    "get_cell_ratio",
    "set_cell_ratio",
    "set_query_timeout",
)
__author__ = "Toluwaleke Ogundipe"

from enum import Enum, auto
from operator import truediv
from typing import Optional, Union

from . import utils
from .exceptions import TermImageError

version_info = (0, 7, 2)

# Follows https://semver.org/spec/v2.0.0.html
__version__ = ".".join(map(str, version_info[:3]))
if version_info[3:]:
    __version__ += "-" + ".".join(map(str, version_info[3:]))

#: Default timeout for :ref:`terminal-queries`
#:
#: See also: :py:func:`set_query_timeout`
DEFAULT_QUERY_TIMEOUT: float = utils._query_timeout  # Final[float]


class AutoCellRatio(Enum):
    """Values for setting :ref:`auto-cell-ratio`."""

    is_supported: Optional[bool]

    FIXED = auto()
    DYNAMIC = auto()


def disable_queries() -> None:
    """Disables :ref:`terminal-queries`.

    To re-enable queries, call :py:func:`enable_queries`.

    NOTE:
        This affects all :ref:`dependent features <queried-features>`.
    """
    utils._queries_enabled = False


def disable_win_size_swap():
    """Disables a workaround for terminal emulators that wrongly report window
    dimensions swapped.

    This workaround is disabled by default. While disabled, the window dimensions
    reported by the :term:`active terminal` are used as-is.

    NOTE:
        This affects :ref:`auto-cell-ratio` computation and size computations for
        :ref:`graphics-based`.
    """
    if utils._swap_win_size:
        utils._swap_win_size = False
        with utils._cell_size_lock:
            utils._cell_size_cache[:] = (0,) * 4


def enable_queries() -> None:
    """Re-Enables :ref:`terminal-queries`.

    Queries are enabled by default. To disable, call :py:func:`disable_queries`.

    NOTE:
        This affects all :ref:`dependent features <queried-features>`.
    """
    if not utils._queries_enabled:
        utils._queries_enabled = True
        utils.get_fg_bg_colors._invalidate_cache()
        utils.get_terminal_name_version._invalidate_cache()
        with utils._cell_size_lock:
            utils._cell_size_cache[:] = (0,) * 4


def enable_win_size_swap():
    """Enables a workaround for terminal emulators that wrongly report window
    dimensions swapped.

    While enabled, the window dimensions reported by the :term:`active terminal` are
    swapped. This workaround is required on some older VTE-based terminal emulators.

    NOTE:
        This affects :ref:`auto-cell-ratio` computation and size computations for
        :ref:`graphics-based`.
    """
    if not utils._swap_win_size:
        utils._swap_win_size = True
        with utils._cell_size_lock:
            utils._cell_size_cache[:] = (0,) * 4


def get_cell_ratio() -> float:
    """Returns the global :term:`cell ratio`.

    See :py:func:`set_cell_ratio`.
    """
    # `(1, 2)` is a fallback in case the terminal doesn't respond in time
    return _cell_ratio or truediv(*(utils.get_cell_size() or (1, 2)))


def set_cell_ratio(ratio: Union[float, AutoCellRatio]) -> None:
    """Sets the global :term:`cell ratio`.

    Args:
        ratio: Can be one of the following values.

          * A positive :py:class:`float` value.
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
            AutoCellRatio.is_supported = utils.get_cell_size() is not None

        if not AutoCellRatio.is_supported:
            raise TermImageError(
                "Auto cell ratio is not supported in the active terminal or on the "
                "current platform"
            )
        elif ratio is AutoCellRatio.FIXED:
            # `(1, 2)` is a fallback in case the terminal doesn't respond in time
            _cell_ratio = truediv(*(utils.get_cell_size() or (1, 2)))
        else:
            _cell_ratio = None
    elif isinstance(ratio, float):
        if ratio <= 0.0:
            raise utils.arg_value_error_range("ratio", ratio)
        _cell_ratio = ratio
    else:
        raise utils.arg_type_error("ratio", ratio)


def set_query_timeout(timeout: float) -> None:
    """Sets the timeout for :ref:`terminal-queries`.

    Args:
        timeout: Time limit for awaiting a response from the terminal, in seconds.

    Raises:
        TypeError: *timeout* is not a float.
        ValueError: *timeout* is less than or equal to zero.
    """
    if not isinstance(timeout, float):
        raise utils.arg_type_error("timeout", timeout)
    if timeout <= 0.0:
        raise utils.arg_value_error_range("timeout", timeout)

    utils._query_timeout = timeout


_cell_ratio = 0.5
AutoCellRatio.is_supported = None
