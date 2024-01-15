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

from typing_extensions import ClassVar, Final

from . import _utils
from ._utils import arg_value_error_range, get_cell_size
from .exceptions import TermImageError

version_info = (0, 8, 0, "dev")

# Follows https://semver.org/spec/v2.0.0.html
__version__ = ".".join(map(str, version_info[:3]))
if version_info[3:]:
    __version__ += "-" + ".".join(map(str, version_info[3:]))

DEFAULT_QUERY_TIMEOUT: Final[float] = _utils._query_timeout
"""Default timeout for :ref:`terminal-queries`

.. seealso:: :py:func:`set_query_timeout`.
"""


class AutoCellRatio(Enum):
    """:ref:`auto-cell-ratio` enumeration and support status.

    .. seealso:: :py:func:`set_cell_ratio`.
    """

    FIXED = auto()
    """Fixed cell ratio.

    :meta hide-value:
    """

    DYNAMIC = auto()
    """Dynamic cell ratio.

    :meta hide-value:
    """

    is_supported: ClassVar[bool | None]
    """Auto cell ratio support status. Can be

    :meta hide-value:

    - ``None`` -> support status not yet determined
    - ``True`` -> supported
    - ``False`` -> not supported

    Can be explicitly set when using auto cell ratio but want to avoid the support
    check in a situation where the support status is foreknown. Can help to avoid
    being wrongly detected as unsupported on a :ref:`queried <terminal-queries>`
    terminal that doesn't respond on time.

    For instance, when using multiprocessing, if the support status has been
    determined in the main process, this value can simply be passed on to and set
    within the child processes.
    """


def disable_queries() -> None:
    """Disables :ref:`terminal-queries`.

    To re-enable queries, call :py:func:`enable_queries`.

    NOTE:
        This affects all :ref:`dependent features <queried-features>`.
    """
    _utils._queries_enabled = False


def disable_win_size_swap() -> None:
    """Disables a workaround for terminal emulators that wrongly report window
    dimensions swapped.

    This workaround is disabled by default. While disabled, the window dimensions
    reported by the :term:`active terminal` are used as-is.

    NOTE:
        This affects :ref:`auto-cell-ratio` computation and size computations for
        :ref:`graphics-based`.
    """
    if _utils._swap_win_size:
        _utils._swap_win_size = False
        with _utils._cell_size_lock:
            _utils._cell_size_cache[:] = (0,) * 4


def enable_queries() -> None:
    """Re-Enables :ref:`terminal-queries`.

    Queries are enabled by default. To disable, call :py:func:`disable_queries`.

    NOTE:
        This affects all :ref:`dependent features <queried-features>`.
    """
    if not _utils._queries_enabled:
        _utils._queries_enabled = True
        getattr(_utils.get_fg_bg_colors, "_invalidate_cache")()
        getattr(_utils.get_terminal_name_version, "_invalidate_cache")()
        with _utils._cell_size_lock:
            _utils._cell_size_cache[:] = (0,) * 4


def enable_win_size_swap() -> None:
    """Enables a workaround for terminal emulators that wrongly report window
    dimensions swapped.

    While enabled, the window dimensions reported by the :term:`active terminal` are
    swapped. This workaround is required on some older VTE-based terminal emulators.

    NOTE:
        This affects :ref:`auto-cell-ratio` computation and size computations for
        :ref:`graphics-based`.
    """
    if not _utils._swap_win_size:
        _utils._swap_win_size = True
        with _utils._cell_size_lock:
            _utils._cell_size_cache[:] = (0,) * 4


def get_cell_ratio() -> float:
    """Returns the global :term:`cell ratio`.

    .. seealso:: :py:func:`set_cell_ratio`.
    """
    # `(1, 2)` is a fallback in case the terminal doesn't respond in time
    return _cell_ratio or truediv(*(get_cell_size() or (1, 2)))


def set_cell_ratio(ratio: float | AutoCellRatio) -> None:
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
        ValueError: *ratio* is a non-positive :py:class:`float`.
        term_image.exceptions.TermImageError: Auto cell ratio is not supported
          in the :term:`active terminal` or on the current platform.

    This value is taken into consideration when setting image sizes for **text-based**
    render styles, in order to preserve the aspect ratio of images drawn to the
    terminal.

    NOTE:
        Changing the cell ratio does not automatically affect any image that has a
        :term:`fixed size`. For a change in cell ratio to take effect, the image's
        size has to be re-set.

    IMPORTANT:
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
    else:
        if ratio <= 0.0:
            raise arg_value_error_range("ratio", ratio)
        _cell_ratio = ratio


def set_query_timeout(timeout: float) -> None:
    """Sets the timeout for :ref:`terminal-queries`.

    Args:
        timeout: Time limit for awaiting a response from the terminal, in seconds.

    Raises:
        ValueError: *timeout* is less than or equal to zero.
    """
    if timeout <= 0.0:
        raise arg_value_error_range("timeout", timeout)

    _utils._query_timeout = timeout


_cell_ratio: float | None = 0.5
AutoCellRatio.is_supported = None
