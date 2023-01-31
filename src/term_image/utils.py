"""
Utilities
=========
"""

from __future__ import annotations

__all__ = (
    "DEFAULT_QUERY_TIMEOUT",
    "DISABLE_QUERIES",
    "SWAP_WIN_SIZE",
    "get_terminal_name_version",
    "get_terminal_size",
    "lock_tty",
    "read_tty_all",
    "set_query_timeout",
    "write_tty",
)

import os
import re
import sys
import warnings
from array import array
from functools import wraps
from multiprocessing import Array, Process, Queue as mp_Queue, RLock as mp_RLock
from operator import floordiv
from queue import Empty, Queue
from shutil import get_terminal_size as _get_terminal_size
from threading import RLock
from time import monotonic
from types import FunctionType
from typing import Callable, Optional, Tuple, Union

from .exceptions import TermImageWarning

# import logging

OS_IS_UNIX: bool
try:
    import fcntl
    import termios
    from select import select
except ImportError:
    OS_IS_UNIX = False
else:
    OS_IS_UNIX = True

#: Default global timeout for :ref:`terminal-queries`
#:
#: See also: :py:func:`set_query_timeout`
DEFAULT_QUERY_TIMEOUT: float = 0.1  #: Final[float]

#: If ``True``, :ref:`terminal-queries` are disabled, thereby affecting all
#: :ref:`dependent features <queried-features>`.
DISABLE_QUERIES: bool = False

#: A workaround for some terminal emulators (e.g older VTE-based ones) that wrongly
#: report window dimensions swapped.
#:
#: | If ``True``, the dimensions reported by the terminal emulator are swapped.
#: | This setting affects :ref:`auto-cell-ratio` computation.
SWAP_WIN_SIZE: bool = False

# Decorator Classes


class ClassInstanceMethod(classmethod):
    """A method which when invoked via the owner, behaves like a class method
    and when invoked via an instance, behaves like an instance method.
    """

    def __get__(self, obj, cls=None):
        # classmethod just uses cls directly if present.
        # Otherwise, type(obj) but we're not concerned with that.
        return super().__get__(None, obj or cls)


# Decorator Functions


def no_redecorate(decor: Callable) -> FunctionType:
    """Prevents a decorator from re-decorating objects.

    Args:
        decor: The decorator to be wrapped.
    """
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
    """Enables return value caching.

    Args:
        func: The function to be wrapped.

    An *_invalidate_cache* function is set as an attribute of the returned wrapper
    which when called clears the cache, so that the next call actually calls the
    wrapped function, no matter the value of *_cached*.

    NOTE:
        It's thread-safe, i.e there is no race condition between calls to the same
        decorated object across threads of the same process.

        Only works when function arguments, if any, are hashable.
    """

    @wraps(func)
    def cached_wrapper(*args, **kwargs):
        arguments = (args, tuple(kwargs.items()))
        with lock:
            try:
                return cache[arguments]
            except KeyError:
                return cache.setdefault(arguments, func(*args, **kwargs))

    def invalidate():
        with lock:
            cache.clear()

    cache = {}
    lock = RLock()
    cached_wrapper._invalidate_cache = invalidate

    return cached_wrapper


@no_redecorate
def lock_tty(func: Callable) -> FunctionType:
    """Synchronizes access to the :term:`active terminal`.

    Args:
        func: The function to be wrapped.

    When any decorated function is called, a re-entrant lock is acquired by the current
    process or thread and released after the call, such that any other decorated
    function called within another thread or subprocess has to wait till the lock is
    fully released (i.e has been released as many times as acquired) by the current
    process or thread.

    NOTE:
        | It automatically works across parent-/sub-processes, started directly or
          indirectly via ``multiprocessing.Process`` (or a subclass of it) and their
          threads.

    IMPORTANT:
        It only works if ``multiprocessing.synchronize`` is supported on the host
        platform.  If not supported, a warning is issued when starting a subprocess.
    """

    @wraps(func)
    def lock_tty_wrapper(*args, **kwargs):
        with _tty_lock:
            # logging.debug(f"{func.__name__} acquired TTY lock", stacklevel=3)
            return func(*args, **kwargs)

    lock_tty_wrapper.__doc__ += """
    HINT:
        Synchronized with :py:func:`lock_tty`.
    """

    return lock_tty_wrapper


@no_redecorate
def terminal_size_cached(func: Callable) -> FunctionType:
    """Enables return value caching based on the size of the :term:`active terminal`.

    Args:
        func: The function to be wrapped.

    If the terminal size is the same as for the last call, the last return value is
    returned. Otherwise the wrapped function is called and the new return value is
    stored and returned.

    An *_invalidate_terminal_size_cache* function is also set as an attribute of the
    returned wrapper which when called clears the cache, so that the next call actually
    calls the wrapped function.

    NOTE:
        It's thread-safe, i.e there is no race condition between calls to the same
        decorated callable across threads of the same process.
    """

    @wraps(func)
    def terminal_size_cached_wrapper(*args, **kwargs):
        with lock:
            ts = get_terminal_size()
            if not cache or ts != cache[1]:
                cache[:] = [func(*args, **kwargs), ts]
        return cache[0]

    def invalidate():
        with lock:
            cache.clear()

    cache = []
    lock = RLock()
    terminal_size_cached_wrapper._invalidate_terminal_size_cache = invalidate

    return terminal_size_cached_wrapper


@no_redecorate
def unix_tty_only(func: Callable) -> FunctionType:
    """Disable invokation of a function on a non-unix-like platform or when there is no
    :term:`active terminal`.

    Args:
        func: The function to be wrapped.
    """

    @wraps(func)
    def unix_only_wrapper(*args, **kwargs):
        return _tty and func(*args, **kwargs)

    unix_only_wrapper.__doc__ += """
    NOTE:
        Currently works on UNIX only, returns ``None`` on any other platform or when
        there is no :term:`active terminal`.
    """

    return unix_only_wrapper


# Non-decorators


def clear_queue(queue: Union[Queue, mp_Queue]):
    """Purges the given queue"""
    while True:
        try:
            queue.get(timeout=0.005)
        except Empty:
            break


def color(
    text: str, fg: Tuple[int] = (), bg: Tuple[int] = (), *, end: bool = False
) -> str:
    """Prepends *text* with 24-bit color escape codes for the given foreground and/or
    background RGB values, optionally ending with the color reset sequence.

    Args:
        text: String to be color-coded.
        fg: Foreground color.
        bg: Background color.
        end: If ``True``, the color reset sequence is appended to the returned string.

    Returns:
        The color-coded string.

    The color code is ommited for any of *fg* or *bg* that is empty.
    """
    return (FG_FMT * bool(fg) + BG_FMT * bool(bg) + "%s") % (
        *fg,
        *bg,
        text,
    ) + COLOR_RESET * end


@unix_tty_only
@terminal_size_cached
def get_cell_size() -> Optional[Tuple[int, int]]:
    """Returns the current size of a character cell in the :term:`active terminal`.

    Returns:
        The terminal cell size in pixels or `None` if undetermined.
    """
    ws = get_window_size()
    size = ws and tuple(map(floordiv, ws, get_terminal_size()))

    return size if size and 0 not in size else None


@cached
def get_fg_bg_colors(
    *, hex: bool = False
) -> Tuple[
    Union[None, str, Tuple[int, int, int]], Union[None, str, Tuple[int, int, int]]
]:
    """Returns the default FG and BG colors of the :term:`active terminal`.

    Returns:
        For each color:

        * an RGB 3-tuple, if *hex* is ``False``
        * an RGB hex string if *hex* is ``True``
        * ``None`` if undetermined
    """
    with _tty_lock:  # All of the terminal's reply isn't read in `query_terminal()`
        response = query_terminal(
            # Not all terminals (e.g VTE-based) support multiple queries in one escape
            # sequence, hence the repetition of OSC ... ST
            f"{OSC}10;?{ST}{OSC}11;?{ST}{CSI}c".encode(),
            # The response might contain a "c"; can't stop reading at "c"
            lambda s: not s.endswith(CSI.encode()),
        )
        if not DISABLE_QUERIES:
            read_tty()  # The rest of the response to `CSI c`

    fg = bg = None
    if response:
        for c, spec in RGB_SPEC.findall(response.decode().rpartition(ESC)[0]):
            if c == "10":
                fg = x_parse_color(spec)
            elif c == "11":
                bg = x_parse_color(spec)

    return tuple(
        rgb and ("#" + ("{:02x}" * 3).format(*rgb) if hex else rgb) for rgb in (fg, bg)
    )


@cached
def get_terminal_name_version() -> Tuple[Optional[str], Optional[str]]:
    """Returns the name and version of the :term:`active terminal`, if available.

    Returns:
        A 2-tuple, ``(name, version)``. If either is not available, returns ``None``
        in its place.
    """
    with _tty_lock:  # the terminal's response to the query is not read all at once
        # Terminal name/version query + terminal attribute query
        # The latter is to speed up the entire query since most (if not all)
        # terminals should support it and most terminals treat queries as FIFO
        response = query_terminal(
            f"{CSI}>q{CSI}c".encode(),
            # The response might contain a "c"; can't stop reading at "c"
            lambda s: not s.endswith(CSI.encode()),
        )
        if not DISABLE_QUERIES:
            read_tty()  # The rest of the response to `CSI c`

    match = response and NAME_VERSION.fullmatch(response.decode().rpartition(ESC)[0])
    name, version = (
        match.groups()
        if match
        else map(os.environ.get, ("TERM_PROGRAM", "TERM_PROGRAM_VERSION"))
    )

    return (name and name.lower(), version)


def get_terminal_size() -> os.terminal_size:
    """Returns the current size of the :term:`active terminal`.

    Returns:
        The terminal size in columns and lines.

    NOTE:
        This implementation is quite different from ``shutil.get_terminal_size()`` and
        ``os.get_terminal_size()`` in that it:

        - gives the correct size of the :term:`active terminal` even when output is
          redirected, in most cases
        - gives different results in certain situations
        - is what this library works with
    """
    if _tty:
        # faster and gives correct results when output is redirected
        try:
            size = os.get_terminal_size(_tty)
        except OSError:
            size = None
    else:
        size = None

    return size or _get_terminal_size()


@unix_tty_only
def get_window_size() -> Optional[Tuple[int, int]]:
    """Returns the current window size of the :term:`active terminal`.

    Returns:
        The terminal size in pixels.

    The speed of this implementation is almost entirely dependent on the terminal; the
    method it supports and its response time if it has to be queried.

    Returns ``None`` if the size couldn't be gotten in time or the terminal lacks
    support.
    """
    with _win_size_lock:
        ts = get_terminal_size()
        if ts == tuple(_win_size_cache[:2]):
            size = tuple(_win_size_cache[2:])
            return None if 0 in size else size

        # First try ioctl
        size = None
        buf = array("H", [0, 0, 0, 0])
        try:
            if not fcntl.ioctl(_tty, termios.TIOCGWINSZ, buf):
                size = tuple(buf[2:])
                if size == (0, 0):
                    size = None
        except OSError:
            pass

        if not size:
            # Then CSI 14 t
            # The second sequence is to speed up the entire query since most (if not
            # all) terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                f"{CSI}14t{CSI}c".encode(), more=lambda s: not s.endswith(b"c")
            )
            size = (response or None) and WIN_SIZE.match(response.decode())
            if size:
                # XTWINOPS specifies (height, width)
                size = tuple(map(int, size.groups()))[::-1]

                # Termux seems to respond with (height / 2, width), though the values
                # are incorrect as they change with different zoom levels but still
                # always give a reasonable (almost always the same) cell size and ratio.
                if os.environ.get("SHELL", "").startswith("/data/data/com.termux/"):
                    size = (size[0], size[1] * 2)

        size = size[:: -SWAP_WIN_SIZE or 1] if size else (0, 0)
        _win_size_cache[:] = ts + size
        return None if 0 in size else size


@unix_tty_only
@lock_tty
def query_terminal(
    request: bytes, more: Callable[[bytearray], bool], timeout: float = None
) -> Optional[bytes]:
    """Sends a query to the :term:`active terminal` and returns the response.

    Args:
        more: A callable, which when passed the response recieved so far, returns a
          boolean indicating if the response is incomplete or not. If it returns:

          * ``True``, more response is waited for.
          * ``False``, the recieved response is returned immediately.

        timeout: Time limit for awaiting a response from the terminal, in seconds
          (infinite if negative).

          If not given or ``None``, the value set by :py:func:`set_query_timeout`
          (or :py:data:`DEFAULT_QUERY_TIMEOUT` if never set) is used.

    Returns:
        `None` if :py:data:`DISABLE_QUERIES` is true, else the terminal's response
        (empty, if no response is recieved after *timeout* is up).

    ATTENTION:
        Any unread input is discared before the query. If the input might be needed,
        it can be read using :py:func:`read_tty()` before calling this fucntion.
    """
    if DISABLE_QUERIES:
        return None

    old_attr = termios.tcgetattr(_tty)
    new_attr = termios.tcgetattr(_tty)
    new_attr[3] &= ~termios.ECHO  # Disable input echo
    try:
        termios.tcsetattr(_tty, termios.TCSAFLUSH, new_attr)
        write_tty(request)
        return read_tty(more, timeout or _query_timeout)
    finally:
        termios.tcsetattr(_tty, termios.TCSANOW, old_attr)


@unix_tty_only
@lock_tty
def read_tty(
    more: Callable[[bytearray], bool] = lambda _: True,
    timeout: Optional[float] = None,
    min: int = 0,
    *,
    echo: bool = False,
) -> bytes:
    """Reads input directly from the :term:`active terminal` with/without blocking.

    Args:
        more: A callable, which when passed the input recieved so far, as a `bytearray`
          object, returns a boolean. If it returns:

          * ``True``, more input is waited for.
          * ``False``, the input recieved so far is returned immediately.

        timeout: Time limit for awaiting input, in seconds.
        min: Causes to block until at least the given number of bytes have been read.
        echo: If ``True``, any input while waiting is printed unto the screen.
          Any input before or after calling this function is not affected.

    Returns:
        The input read (empty, if *min* == ``0`` (default) and no input is recieved
        before *timeout* is up).

    If *timeout* is ``None`` (default), all available input is read without blocking.

    If *timeout* is not ``None`` and:

      * *timeout* < ``0``, it's infinite.
      * *min* > ``0``, input is waited for until at least *min* bytes have been read.

        After *min* bytes have been read, the following points apply with *timeout*
        being the leftover of the original *timeout*, if not yet used up.

      * *more* is not given, input is read or waited for until *timeout* is up.
      * *more* is given, input is read or waited for until ``more(input)`` returns
        ``False`` or *timeout* is up.

    Upon return or interruption, the :term:`active terminal` is **immediately** restored
    to the state in which it was met.
    """
    old_attr = termios.tcgetattr(_tty)
    new_attr = termios.tcgetattr(_tty)
    new_attr[3] &= ~termios.ICANON  # Disable cannonical mode
    new_attr[6][termios.VTIME] = 0  # Never block based on time
    if echo:
        new_attr[3] |= termios.ECHO  # Enable input echo
    else:
        new_attr[3] &= ~termios.ECHO  # Disable input echo
    # Block until *min* bytes are read, when *timeout* is not `None`.
    new_attr[6][termios.VMIN] = 0 if timeout is None else min

    input = bytearray()
    try:
        termios.tcsetattr(_tty, termios.TCSANOW, new_attr)
        r, w, x = [_tty], [], []

        if timeout is None:
            # VMIN=0 does not work as expected on some platforms when there's no input
            while select(r, w, x, 0.0)[0]:
                input.extend(os.read(_tty, 100))
        else:
            start = monotonic()
            if min > 0:
                input.extend(os.read(_tty, min))

                # Don't block based on based on amount of bytes anymore
                new_attr[6][termios.VMIN] = 0
                termios.tcsetattr(_tty, termios.TCSANOW, new_attr)

            duration = monotonic() - start
            while (timeout < 0 or duration < timeout) and more(input):
                # Reduces CPU usage
                # Also, VMIN=0 does not work on some platforms when there's no input
                if select(r, w, x, None if timeout < 0 else timeout - duration)[0]:
                    input.extend(os.read(_tty, 1))
                duration = monotonic() - start
            # logging.debug(duration)
    finally:
        termios.tcsetattr(_tty, termios.TCSANOW, old_attr)

    return bytes(input)


@unix_tty_only
def read_tty_all() -> bytes:
    """Reads all available input directly from the :term:`active terminal` **without
    blocking**.

    Returns:
        The input read.

    HINT:
        Synchronized with :py:func:`lock_tty`.
    """
    return read_tty()


def set_query_timeout(timeout: float) -> None:
    """Sets the global timeout for :ref:`terminal-queries`.

    Args:
        timeout: Time limit for awaiting a response from the terminal, in seconds.

    Raises:
        TypeError: *timeout* is not a float.
        ValueError: *timeout* is less than or equal to zero.
    """
    global _query_timeout

    if not isinstance(timeout, float):
        raise TypeError(f"'timeout' must be a float (got: {type(timeout).__name__!r})")
    if timeout <= 0.0:
        raise ValueError(f"'timeout' must be greater than zero (got: {timeout!r})")

    _query_timeout = timeout


@unix_tty_only
@lock_tty
def write_tty(data: bytes) -> None:
    """Writes to the :term:`active terminal` and waits until complete transmission.

    Args:
        data: Data to be written.
    """
    os.write(_tty, data)
    try:
        termios.tcdrain(_tty)
    except termios.error:  # "Permission denied" on some platforms e.g Termux
        pass


def x_parse_color(spec: str) -> Tuple[int, int, int]:
    """Converts an RGB device specification according to XParseColor"""
    # One hex char -> 4 bits
    return tuple(int(x, 16) * 255 // ((1 << (len(x) * 4)) - 1) for x in spec.split("/"))


def _process_start_wrapper(self, *args, **kwargs):
    global _tty_lock, _win_size_cache, _win_size_lock

    # Ensure it's not acquired by another process/thread before changing it.
    # The only way this can be countered is if the owner thread is the
    # one starting a process, which is very unlikely within a function meant
    # for input/output :|
    with _tty_lock:
        if isinstance(_tty_lock, type(RLock())):
            try:
                self._tty_lock = _tty_lock = mp_RLock()
            except ImportError:
                self._tty_lock = None
                warnings.warn(
                    "Multi-process synchronization is not supported on this platform!\n"
                    "Hence, if any subprocess will be writing/reading to/from the "
                    "active terminal, it may be unsafe to use any features requiring"
                    "terminal queries.\n"
                    "See https://term-image.readthedocs.io/en/stable/library/reference"
                    "/utils.html#terminal-queries\n"
                    "If any related issues occur, it's advisable to set "
                    "`term_image.utils.DISABLE_QUERIES = True`.\n"
                    "Simply set an 'ignore' filter for this warning (before starting "
                    "any subprocess) if not using any of the affected features.",
                    TermImageWarning,
                )
        else:
            self._tty_lock = _tty_lock

    with _win_size_lock:
        if isinstance(_win_size_lock, type(RLock())):
            try:
                self._win_size_cache = _win_size_cache = Array("i", _win_size_cache)
                _win_size_lock = _win_size_cache.get_lock()
            except ImportError:
                self._win_size_cache = None
        else:
            self._win_size_cache = _win_size_cache

    return _process_start_wrapper.__wrapped__(self, *args, **kwargs)


def _process_run_wrapper(self, *args, set_tty_lock: bool = True, **kwargs):
    global _tty_lock, _win_size_cache, _win_size_lock

    if set_tty_lock:
        if self._tty_lock:
            _tty_lock = self._tty_lock
        if self._win_size_cache:
            _win_size_cache = self._win_size_cache
            _win_size_lock = _win_size_cache.get_lock()

    return _process_run_wrapper.__wrapped__(self, *args, **kwargs)


RGB_SPEC = re.compile(r"\033](\d+);rgb:([\da-fA-F/]+)\033\\", re.ASCII)
WIN_SIZE = re.compile(r"\033\[4;(\d+);(\d+)t", re.ASCII)
NAME_VERSION = re.compile(r"\033P>\|(\w+)[( ]([^)\033]+)\)?\033\\", re.ASCII)

# Constants for escape sequences
ESC = "\033"
CSI = f"{ESC}["
OSC = f"{ESC}]"
ST = f"{ESC}\\"
BG_FMT = f"{CSI}48;2;%d;%d;%dm"
FG_FMT = f"{CSI}38;2;%d;%d;%dm"
COLOR_RESET = f"{CSI}m"

# Private internal variables
_query_timeout = DEFAULT_QUERY_TIMEOUT
_tty: Optional[int] = None
_tty_lock = RLock()
_win_size_cache = [0] * 4
_win_size_lock = RLock()

if OS_IS_UNIX:
    for stream in ("out", "in", "err"):  # In order of priority
        try:
            _tty = os.ttyname(getattr(sys, f"__std{stream}__").fileno())
            break
        except (OSError, AttributeError):
            pass
    else:
        try:
            _tty = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
        except OSError:
            warnings.warn(
                "It seems this process is not running within a terminal. "
                "Hence, some features will behave differently or be disabled.\n"
                "See https://term-image.readthedocs.io/en/stable/library/reference"
                "/utils.html#terminal-queries\n"
                "You can set an 'ignore' filter for this warning before loading "
                "`term_image`, if not using any of the features affected.",
                TermImageWarning,
            )
    if _tty:
        if isinstance(_tty, str):
            _tty = os.open(_tty, os.O_RDWR)

        Process.start = wraps(Process.start)(_process_start_wrapper)
        Process.run = wraps(Process.run)(_process_run_wrapper)

        # Shouldn't be needed since we're getting our own separate file descriptors
        # but the validity of the assumed safety is stil under probation
        """
        for name, value in vars(termios).items():
            if isinstance(value, BuiltinFunctionType):
                setattr(termios, name, lock_tty(value))
        """
