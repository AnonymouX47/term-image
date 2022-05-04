from __future__ import annotations

__all__ = (
    "OS_IS_UNIX",
    "no_redecorate",
    "cached",
    "unix_tty_only",
    "terminal_size_cached",
    "color",
)

import os
import sys
import warnings
from functools import wraps
from shutil import get_terminal_size
from threading import RLock
from types import FunctionType
from typing import Callable, Optional

OS_IS_UNIX: bool
try:
    import fcntl  # noqa:F401
    import termios  # noqa:F401
except ImportError:
    OS_IS_UNIX = False
else:
    OS_IS_UNIX = True

# Decorators


def no_redecorate(decor: Callable) -> FunctionType:
    """Decorates a decorator to prevent it from re-decorating objects."""
    if getattr(decor, "_no_redecorate_", False):
        return decor

    @wraps(decor)
    def no_redecorate_wrapper(obj, *args, **kwargs):
        if not getattr(obj, f"_{decor.__name__}_", False):
            obj = decor(obj, *args, **kwargs)
            setattr(obj, f"_{decor.__name__}_", True)
        return obj

    no_redecorate_wrapper._no_redecorate_ = True
    return no_redecorate_wrapper


@no_redecorate
def cached(func: Callable) -> FunctionType:
    """Enables return value caching on the decorated callable.

    The wrapper adds a *_cached* keyword-only parameter. When *_cached* is:

      - `False` (default), the wrapped function is called and its return value is stored
        and returned.
      - `True`, the last stored value is returned.

    An *_invalidate_cache* function is also set as an attribute of the returned wrapper
    which when called clears the cache, so that the next call actually calls the
    wrapped function, no matter the value of *_cached*.

    NOTE:
        It's thread-safe, i.e there is no race condition between calls to the same
        decorated callable across threads of the same process.
    """

    @wraps(func)
    def cached_wrapper(*args, _cached: bool = False, **kwargs):
        with lock:
            if not _cached or not cache:
                cache[:] = (func(*args, **kwargs),)
        return cache[0]

    cache = []
    lock = RLock()
    cached_wrapper._invalidate_cache = cache.clear

    return cached_wrapper


@no_redecorate
def unix_tty_only(func: Callable) -> FunctionType:
    """Any decorated callable always returns ``None`` on a non-unix-like platform
    or when the process fails to gain direct access to the terminal.
    """

    @wraps(func)
    def unix_only_wrapper(*args, **kwargs):
        return _tty and func(*args, **kwargs)

    return unix_only_wrapper


@no_redecorate
def terminal_size_cached(func: Callable) -> FunctionType:
    """Enables return value caching on the decorated callable, based on the current
    terminal size.

    If the terminal size is the same as for the last call, the last return value is
    returned. Otherwise the wrapped object is called and the new return value is
    stored and returned.

    It's thread-safe, i.e there is no race condition between calls to the same
    decorated callable across threads of the same process.

    An *_invalidate_terminal_size_cache* function is also set as an attribute of the
    returned wrapper which when called clears the cache, so that the next call actually
    calls the wrapped function.
    """

    @wraps(func)
    def terminal_size_cached_wrapper(*args, **kwargs):
        with lock:
            ts = get_terminal_size()
            if not cache or ts != cache[1]:
                cache[:] = [func(*args, **kwargs), ts]
        return cache[0]

    cache = []
    terminal_size_cached_wrapper._invalidate_terminal_size_cache = cache.clear
    lock = RLock()

    return terminal_size_cached_wrapper


# Non-decorators


def color(
    text: str, fg: Tuple[int] = (), bg: Tuple[int] = (), *, end: bool = False
) -> str:
    """Prepends *text* with 24-bit color escape codes for the given foreground and/or
    background RGB values, optionally ending with the color reset sequence.

    The color code is ommited for any of *fg* or *bg* that is empty.
    """
    return (_FG_FMT * bool(fg) + _BG_FMT * bool(bg) + "%s") % (
        *fg,
        *bg,
        text,
    ) + _RESET * end


_BG_FMT = "\033[48;2;%d;%d;%dm"
_FG_FMT = "\033[38;2;%d;%d;%dm"
_RESET = "\033[0m"

# Appended to ensure it is overriden by any filter prepended before loading this module
warnings.filterwarnings("default", category=UserWarning, module=__name__, append=True)

_tty: Optional[int] = None
if OS_IS_UNIX:
    # In order of probability of being available and being a TTY
    try:
        _tty = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    except OSError:
        try:
            _tty = os.ttyname(sys.__stderr__.fileno())
        except (OSError, AttributeError):
            try:
                _tty = os.ttyname(sys.__stdin__.fileno())
            except (OSError, AttributeError):
                try:
                    _tty = os.ttyname(sys.__stdout__.fileno())
                except (OSError, AttributeError):
                    warnings.warn(
                        "It seems this process is not running within a terminal. "
                        "Hence, automatic font ratio and render styles based on "
                        "terminal graphics protocols will not work.\n"
                        "You can set an 'ignore' filter for this warning before "
                        "loading `term_image`, if not using any of the features "
                        "affected.",
                        UserWarning,
                    )
    if _tty:
        if isinstance(_tty, str):
            _tty = os.open(_tty, os.O_RDWR)
