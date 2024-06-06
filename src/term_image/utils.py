"""
.. Utilities
"""

from __future__ import annotations

__all__ = (
    "get_cell_size",
    "get_terminal_name_version",
    "get_terminal_size",
    "lock_tty",
    "read_tty_all",
    "write_tty",
)

import os
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
from typing import Any, Callable, Optional, Tuple, Union

from . import ctlseqs
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

# NOTE: Any cached feature using a query should have it's cache invalidated in
# `term_image.enable_queries()`.

# Decorator Classes


class ClassInstanceMethod(classmethod):
    """A method which when invoked via the owner, behaves like a class method
    and when invoked via an instance, behaves like an instance method.
    """

    def __init__(
        self, f_owner: FunctionType, f_instance: Optional[FunctionType] = None
    ):
        super().__init__(f_owner)
        self.f_owner = f_owner
        self.f_instance = f_instance

    def __get__(self, instance, owner=None):
        if instance:
            return self.f_instance.__get__(instance, owner)
        else:
            return super().__get__(instance, owner)

    def classmethod(self, function: FunctionType) -> ClassInstanceMethod:
        return type(self)(function, self.f_instance)

    def instancemethod(self, function: FunctionType) -> ClassInstanceMethod:
        return type(self)(self.f_owner, function)


class ClassPropertyBase(property):
    """Base class for owner properties that also have a counterpart/shadow on the
    instance.
    """

    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        super().__init__(fget, fset, fdel, doc)
        # `property` doesn't set `__doc__`, probably cos the subclass' `__doc__`
        # attribute overrides its `__doc__` descriptor.
        super().__setattr__("__doc__", doc or fget.__doc__)


class ClassInstanceProperty(ClassPropertyBase):
    """A an instance-specific counterpart of a property of the owner.

    Operation on the owner is actually implemented by a property defined on the
    owner's metaclass. This class is only for the sake of ease of documentation
    without having to bother the user about metaclasses.
    """


class ClassProperty(ClassPropertyBase):
    """A read-only shadow of a property of the owner.

    Operation on the owner is actually implemented by a property defined on the
    owner's metaclass. This class is only for the sake of ease of documentation
    without having to bother the user about metaclasses.
    """


# Decorator Functions


def no_redecorate(decor: FunctionType) -> FunctionType:
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
def cached(func: FunctionType) -> FunctionType:
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
def lock_tty(func: FunctionType) -> FunctionType:
    """Synchronizes access to the :term:`active terminal`.

    Args:
        func: The function to be wrapped.

    When a decorated function is called, a re-entrant lock is acquired by the current
    process or thread and released after the call, such that any other decorated
    function called within another thread or subprocess waits until the lock is
    fully released (i.e has been released as many times as acquired) by the current
    process or thread.

    NOTE:
        It works across parent-/sub-processes, started directly or indirectly via
        :py:class:`multiprocessing.Process` (or a subclass of it), and their threads,
        provided :py:mod:`multiprocessing.synchronize` is supported on the host
        platform. Otherwise, a warning is issued when starting a subprocess.

    WARNING:
        If :py:mod:`multiprocessing.synchronize` is supported and a subprocess is
        started within a call (possibly recursive) to a decorated function, the thread
        in which that occurs will be out of sync until that call returns.
        Hence, avoid starting a subprocess within a decorated function.
    """

    @wraps(func)
    def lock_tty_wrapper(*args, **kwargs):
        # If a thread reaches this point while the lock is being changed
        # (the old lock has been acquired but hasn't been changed), after the lock has
        # been changed and the former lock is released, the waiting thread will acquire
        # the old lock making it to be out of sync.
        # Hence the second expression, which allows such a thread to acquire the new
        # lock and be in sync.
        # NB: Multiple expressions are processed as multiple nested with statements.
        with _tty_lock, _tty_lock:
            # logging.debug(f"{func.__name__} acquired TTY lock", stacklevel=3)
            return func(*args, **kwargs)

    if func.__module__.startswith("term_image") and func.__doc__ is not None:
        sync_doc = """

        IMPORTANT:
            Synchronized with :py:func:`~term_image.utils.lock_tty`.
        """

        last_line = func.__doc__.rpartition("\n")[2]
        indent = " " * (len(last_line) - len(last_line.lstrip()))
        lock_tty_wrapper.__doc__ = func.__doc__.rstrip() + "\n".join(
            line.replace(" " * 8, indent, 1) for line in sync_doc.splitlines()
        )

    return lock_tty_wrapper


@no_redecorate
def terminal_size_cached(func: FunctionType) -> FunctionType:
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
def unix_tty_only(func: FunctionType) -> FunctionType:
    """Disable invocation of a function on a non-unix-like platform or when there is no
    :term:`active terminal`.

    Args:
        func: The function to be wrapped.
    """

    @wraps(func)
    def unix_only_wrapper(*args, **kwargs):
        return _tty_fd and func(*args, **kwargs)

    unix_only_wrapper.__doc__ += """
    NOTE:
        Currently works on UNIX only, returns ``None`` on any other platform or when
        there is no :term:`active terminal`.
    """

    return unix_only_wrapper


# Non-decorators


def arg_type_error(arg: str, value: Any) -> TypeError:
    return TypeError(f"Invalid type for {arg!r} (got: {type(value).__name__})")


def arg_value_error(arg: str, value: Any) -> ValueError:
    return ValueError(f"Invalid value for {arg!r} (got: {value!r})")


def arg_value_error_msg(msg: str, value: Any) -> ValueError:
    return ValueError(f"{msg} (got: {value!r})")


def arg_value_error_range(arg: str, value: Any, got_extra: str = "") -> ValueError:
    return ValueError(
        f"{arg!r} out of range (got: {value!r}, {got_extra})"
        if got_extra
        else f"{arg!r} out of range (got: {value!r})"
    )


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

    The color code is omitted for any of *fg* or *bg* that is empty.
    """
    return (ctlseqs.SGR_FG_RGB * bool(fg) + ctlseqs.SGR_BG_RGB * bool(bg) + "%s") % (
        *fg,
        *bg,
        text,
    ) + ctlseqs.SGR_NORMAL * end


@unix_tty_only
def get_cell_size() -> Optional[Tuple[int, int]]:
    """Returns the current size of a character cell in the :term:`active terminal`.

    Returns:
        The cell size in pixels or `None` if undetermined.

    The speed of this implementation is almost entirely dependent on the terminal; the
    method it supports and its response time if it has to be queried.
    """
    # If a thread reaches this point while the lock is being changed
    # (the old lock has been acquired but hasn't been changed), after the lock has
    # been changed and the former lock is released, the waiting thread will acquire
    # the old lock making it to be out of sync.
    # Hence the second expression, which allows such a thread to acquire the new
    # lock and be in sync.
    # NB: Multiple expressions are processed as multiple nested with statements.
    with _cell_size_lock, _cell_size_lock:
        ts = get_terminal_size()
        if ts == tuple(_cell_size_cache[:2]):
            size = tuple(_cell_size_cache[2:])
            return None if 0 in size else size

        size = text_area_size = None

        # First try ioctl
        buf = array("H", [0, 0, 0, 0])
        try:
            if not fcntl.ioctl(_tty_fd, termios.TIOCGWINSZ, buf):
                text_area_size = tuple(buf[2:])
                if 0 in text_area_size:
                    text_area_size = None
        except OSError:
            pass

        if not text_area_size:
            # Then XTWINOPS
            # The last sequence is to speed up the entire query since most (if not all)
            # terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                ctlseqs.CELL_SIZE_PX_b + ctlseqs.TEXT_AREA_SIZE_PX_b + ctlseqs.DA1_b,
                more=lambda s: not s.endswith(b"c"),
            )
            if response:
                cell_size_match = ctlseqs.CELL_SIZE_PX_re.match(response.decode())
                if not cell_size_match:
                    text_area_size_match = ctlseqs.TEXT_AREA_SIZE_PX_re.match(
                        response.decode()
                    )

                # XTWINOPS specifies (height, width)
                if cell_size_match:
                    size = tuple(map(int, cell_size_match.groups()))[::-1]
                elif text_area_size_match:
                    text_area_size = tuple(  # fmt: skip
                        map(int, text_area_size_match.groups())
                    )[::-1]

                    # Termux seems to respond with (height / 2, width), though the
                    # values are incorrect as they change with different zoom levels
                    # but still always give a reasonable (almost always the same)
                    # cell size and ratio.
                    if os.environ.get("SHELL", "").startswith("/data/data/com.termux/"):
                        text_area_size = (text_area_size[0], text_area_size[1] * 2)

        if text_area_size and _swap_win_size:
            text_area_size = text_area_size[::-1]
        size = size or (
            tuple(map(floordiv, text_area_size, ts)) if text_area_size else (0, 0)
        )
        _cell_size_cache[:] = ts + size

        return None if 0 in size else size


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
    # The terminal's response to the queries is not read all at once
    with _tty_lock, _tty_lock:  # See the comment in `lock_tty_wrapper()`
        response = query_terminal(
            # Not all terminals (e.g VTE-based) support multiple queries in one escape
            # sequence, hence the separate sequences for FG and BG
            ctlseqs.TEXT_FG_QUERY_b + ctlseqs.TEXT_BG_QUERY_b + ctlseqs.DA1_b,
            # The response might contain a "c"; can't stop reading at "c"
            lambda s: not s.endswith(ctlseqs.CSI_b),
        )
        if _queries_enabled:
            read_tty()  # The rest of the response to DA1

    fg = bg = None
    if response:
        for c, spec in ctlseqs.RGB_SPEC_re.findall(response.decode()):
            if c == "10":
                fg = ctlseqs.x_parse_color(spec)
            elif c == "11":
                bg = ctlseqs.x_parse_color(spec)

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
    # The terminal's response to the queries is not read all at once
    with _tty_lock, _tty_lock:  # See the comment in `lock_tty_wrapper()`
        # Terminal name/version query + terminal attribute query
        # The latter is to speed up the entire query since most (if not all)
        # terminals should support it and most terminals treat queries as FIFO
        response = query_terminal(
            ctlseqs.XTVERSION_b + ctlseqs.DA1_b,
            # The response might contain a "c"; can't stop reading at "c"
            lambda s: not s.endswith(ctlseqs.CSI_b),
        )
        if _queries_enabled:
            read_tty()  # The rest of the response to DA1

    match = response and ctlseqs.XTVERSION_re.match(response.decode())
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
        This implementation is quite different from :py:func:`shutil.get_terminal_size`
        and :py:func:`os.get_terminal_size` in that it:

        - gives the correct size of the :term:`active terminal` even when output is
          redirected, in most cases
        - gives different results in certain situations
        - is what this library works with
    """
    if _tty_fd:
        # faster and gives correct results when output is redirected
        try:
            size = os.get_terminal_size(_tty_fd)
        except OSError:
            size = None
    else:
        size = None

    return size or _get_terminal_size()


@unix_tty_only
@lock_tty
def query_terminal(
    request: bytes, more: Callable[[bytearray], bool], timeout: float = None
) -> Optional[bytes]:
    """Sends a query to the :term:`active terminal` and returns the response.

    Args:
        more: A callable, which when passed the response received so far, returns a
          boolean indicating if the response is incomplete or not. If it returns:

          * ``True``, more response is waited for.
          * ``False``, the received response is returned immediately.

        timeout: Time limit for awaiting a response from the terminal, in seconds
          (infinite if negative).

          If not given or ``None``, the value set by
          :py:func:`~term_image.set_query_timeout`
          (or :py:data:`~term_image.DEFAULT_QUERY_TIMEOUT` if never set) is used.

    Returns:
        `None` if queries are disabled (via :py:func:`~term_image.disable_queries`),
        else the terminal's response (empty, if no response is received after
        *timeout* is up).

    ATTENTION:
        Any unread input is discarded before the query. If the input might be needed,
        it can be read using :py:func:`read_tty()` before calling this function.
    """
    if not _queries_enabled:
        return None

    old_attr = termios.tcgetattr(_tty_fd)
    new_attr = termios.tcgetattr(_tty_fd)
    new_attr[3] &= ~termios.ECHO  # Disable input echo
    try:
        termios.tcsetattr(_tty_fd, termios.TCSAFLUSH, new_attr)
        write_tty(request)
        return read_tty(more, timeout or _query_timeout)
    finally:
        termios.tcsetattr(_tty_fd, termios.TCSANOW, old_attr)


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
        more: A callable, which when passed the input received so far, as a `bytearray`
          object, returns a boolean. If it returns:

          * ``True``, more input is waited for.
          * ``False``, the input received so far is returned immediately.

        timeout: Time limit for awaiting input, in seconds.
        min: Causes to block until at least the given number of bytes have been read.
        echo: If ``True``, any input while waiting is printed unto the screen.
          Any input before or after calling this function is not affected.

    Returns:
        The input read (empty, if *min* == ``0`` (default) and no input is received
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
    old_attr = termios.tcgetattr(_tty_fd)
    new_attr = termios.tcgetattr(_tty_fd)
    new_attr[3] &= ~termios.ICANON  # Disable canonical mode
    new_attr[6][termios.VTIME] = 0  # Never block based on time
    if echo:
        new_attr[3] |= termios.ECHO  # Enable input echo
    else:
        new_attr[3] &= ~termios.ECHO  # Disable input echo
    # Block until *min* bytes are read, when *timeout* is not `None`.
    new_attr[6][termios.VMIN] = 0 if timeout is None else min

    input = bytearray()
    try:
        termios.tcsetattr(_tty_fd, termios.TCSANOW, new_attr)
        r, w, x = [_tty_fd], [], []

        if timeout is None:
            # VMIN=0 does not work as expected on some platforms when there's no input
            while select(r, w, x, 0.0)[0]:
                input.extend(os.read(_tty_fd, 100))
        else:
            start = monotonic()
            if min > 0:
                input.extend(os.read(_tty_fd, min))

                # Don't block based on based on amount of bytes anymore
                new_attr[6][termios.VMIN] = 0
                termios.tcsetattr(_tty_fd, termios.TCSANOW, new_attr)

            duration = monotonic() - start
            while (timeout < 0 or duration < timeout) and more(input):
                # Reduces CPU usage
                # Also, VMIN=0 does not work on some platforms when there's no input
                if select(r, w, x, None if timeout < 0 else timeout - duration)[0]:
                    input.extend(os.read(_tty_fd, 1))
                duration = monotonic() - start
            # logging.debug(duration)
    finally:
        termios.tcsetattr(_tty_fd, termios.TCSANOW, old_attr)

    return bytes(input)


@unix_tty_only
def read_tty_all() -> bytes:
    """Reads all available input directly from the :term:`active terminal` **without
    blocking**.

    Returns:
        The input read.

    IMPORTANT:
        Synchronized with :py:func:`~term_image.utils.lock_tty`.
    """
    return read_tty()


@unix_tty_only
@lock_tty
def write_tty(data: bytes) -> None:
    """Writes to the :term:`active terminal` and waits until complete transmission.

    Args:
        data: Data to be written.
    """
    os.write(_tty_fd, data)
    try:
        termios.tcdrain(_tty_fd)
    except termios.error:  # "Permission denied" on some platforms e.g Termux
        pass


def _process_start_wrapper(self, *args, **kwargs):
    global _tty_lock, _cell_size_cache, _cell_size_lock

    # Ensure a lock is not acquired by another process/thread before changing it.
    # The only case in which this is useless is when the owner thread is the
    # one starting a process. In such a situation, the owner thread will be partially
    # (may acquire the new lock in a nested call while still holding the old lock)
    # out of sync until it has fully released the old lock.

    with _tty_lock:
        if isinstance(_tty_lock, _rlock_type):
            try:
                self._tty_lock = _tty_lock = mp_RLock()
            except ImportError:
                self._tty_lock = None
                warnings.warn(
                    "Multi-process synchronization is not supported on this platform!\n"
                    "Hence, if any subprocess will be writing/reading to/from the "
                    "active terminal, it may be unsafe to use any features requiring"
                    "terminal queries.\n"
                    "See https://term-image.readthedocs.io/en/stable/guide/concepts"
                    ".html#terminal-queries\n"
                    "If any related issues occur, it's advisable to disable queries "
                    "using `term_image.disable_queries()`.\n"
                    "Simply set an 'ignore' filter for this warning (before starting "
                    "any subprocess) if not using any of the affected features.",
                    TermImageWarning,
                )
        else:
            self._tty_lock = _tty_lock

    with _cell_size_lock:
        if isinstance(_cell_size_lock, _rlock_type):
            try:
                self._cell_size_cache = _cell_size_cache = Array("i", _cell_size_cache)
                _cell_size_lock = _cell_size_cache.get_lock()
            except ImportError:
                self._cell_size_cache = None
        else:
            self._cell_size_cache = _cell_size_cache

    return _process_start_wrapper.__wrapped__(self, *args, **kwargs)


def _process_run_wrapper(self, *args, **kwargs):
    global _tty_lock, _cell_size_cache, _cell_size_lock

    if self._tty_lock:
        _tty_lock = self._tty_lock
    if self._cell_size_cache:
        _cell_size_cache = self._cell_size_cache
        _cell_size_lock = _cell_size_cache.get_lock()

    return _process_run_wrapper.__wrapped__(self, *args, **kwargs)


# Private internal variables
_query_timeout = 0.1
_queries_enabled: bool = True
_swap_win_size: bool = False
_tty_fd: Optional[int] = None
_tty_lock = RLock()
_cell_size_cache = [0] * 4
_cell_size_lock = RLock()
_rlock_type = type(_tty_lock)

if OS_IS_UNIX:
    for stream in ("out", "in", "err"):  # In order of priority
        try:
            _tty_fd = os.ttyname(getattr(sys, f"__std{stream}__").fileno())
            break
        except (OSError, AttributeError):
            pass
    else:
        try:
            _tty_fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
        except OSError:
            warnings.warn(
                "It seems this process is not running within a terminal. "
                "Hence, some features will behave differently or be disabled.\n"
                "See https://term-image.readthedocs.io/en/stable/guide/concepts"
                ".html#active-terminal\n"
                "Any filter for this warning must be set before loading `term_image`, "
                "using `UserWarning` with the warning message (since "
                "`TermImageWarning` won't be available).",
                TermImageWarning,
            )
    if _tty_fd:
        if isinstance(_tty_fd, str):
            _tty_fd = os.open(_tty_fd, os.O_RDWR)

        Process.start = wraps(Process.start)(_process_start_wrapper)
        Process.run = wraps(Process.run)(_process_run_wrapper)

        # Shouldn't be needed since we're getting our own separate file descriptors
        # but the validity of the assumed safety is still under probation
        """
        for name, value in vars(termios).items():
            if isinstance(value, BuiltinFunctionType):
                setattr(termios, name, lock_tty(value))
        """

XTERM_256_PALETTE = (
    0, 0, 0,
    205, 0, 0,
    0, 205, 0,
    205, 205, 0,
    0, 0, 238,
    205, 0, 205,
    0, 205, 205,
    229, 229, 229,
    127, 127, 127,
    255, 0, 0,
    0, 255, 0,
    255, 255, 0,
    92, 92, 255,
    255, 0, 255,
    0, 255, 255,
    255, 255, 255,
    0, 0, 0,
    0, 0, 95,
    0, 0, 135,
    0, 0, 175,
    0, 0, 215,
    0, 0, 255,
    0, 95, 0,
    0, 95, 95,
    0, 95, 135,
    0, 95, 175,
    0, 95, 215,
    0, 95, 255,
    0, 135, 0,
    0, 135, 95,
    0, 135, 135,
    0, 135, 175,
    0, 135, 215,
    0, 135, 255,
    0, 175, 0,
    0, 175, 95,
    0, 175, 135,
    0, 175, 175,
    0, 175, 215,
    0, 175, 255,
    0, 215, 0,
    0, 215, 95,
    0, 215, 135,
    0, 215, 175,
    0, 215, 215,
    0, 215, 255,
    0, 255, 0,
    0, 255, 95,
    0, 255, 135,
    0, 255, 175,
    0, 255, 215,
    0, 255, 255,
    95, 0, 0,
    95, 0, 95,
    95, 0, 135,
    95, 0, 175,
    95, 0, 215,
    95, 0, 255,
    95, 95, 0,
    95, 95, 95,
    95, 95, 135,
    95, 95, 175,
    95, 95, 215,
    95, 95, 255,
    95, 135, 0,
    95, 135, 95,
    95, 135, 135,
    95, 135, 175,
    95, 135, 215,
    95, 135, 255,
    95, 175, 0,
    95, 175, 95,
    95, 175, 135,
    95, 175, 175,
    95, 175, 215,
    95, 175, 255,
    95, 215, 0,
    95, 215, 95,
    95, 215, 135,
    95, 215, 175,
    95, 215, 215,
    95, 215, 255,
    95, 255, 0,
    95, 255, 95,
    95, 255, 135,
    95, 255, 175,
    95, 255, 215,
    95, 255, 255,
    135, 0, 0,
    135, 0, 95,
    135, 0, 135,
    135, 0, 175,
    135, 0, 215,
    135, 0, 255,
    135, 95, 0,
    135, 95, 95,
    135, 95, 135,
    135, 95, 175,
    135, 95, 215,
    135, 95, 255,
    135, 135, 0,
    135, 135, 95,
    135, 135, 135,
    135, 135, 175,
    135, 135, 215,
    135, 135, 255,
    135, 175, 0,
    135, 175, 95,
    135, 175, 135,
    135, 175, 175,
    135, 175, 215,
    135, 175, 255,
    135, 215, 0,
    135, 215, 95,
    135, 215, 135,
    135, 215, 175,
    135, 215, 215,
    135, 215, 255,
    135, 255, 0,
    135, 255, 95,
    135, 255, 135,
    135, 255, 175,
    135, 255, 215,
    135, 255, 255,
    175, 0, 0,
    175, 0, 95,
    175, 0, 135,
    175, 0, 175,
    175, 0, 215,
    175, 0, 255,
    175, 95, 0,
    175, 95, 95,
    175, 95, 135,
    175, 95, 175,
    175, 95, 215,
    175, 95, 255,
    175, 135, 0,
    175, 135, 95,
    175, 135, 135,
    175, 135, 175,
    175, 135, 215,
    175, 135, 255,
    175, 175, 0,
    175, 175, 95,
    175, 175, 135,
    175, 175, 175,
    175, 175, 215,
    175, 175, 255,
    175, 215, 0,
    175, 215, 95,
    175, 215, 135,
    175, 215, 175,
    175, 215, 215,
    175, 215, 255,
    175, 255, 0,
    175, 255, 95,
    175, 255, 135,
    175, 255, 175,
    175, 255, 215,
    175, 255, 255,
    215, 0, 0,
    215, 0, 95,
    215, 0, 135,
    215, 0, 175,
    215, 0, 215,
    215, 0, 255,
    215, 95, 0,
    215, 95, 95,
    215, 95, 135,
    215, 95, 175,
    215, 95, 215,
    215, 95, 255,
    215, 135, 0,
    215, 135, 95,
    215, 135, 135,
    215, 135, 175,
    215, 135, 215,
    215, 135, 255,
    215, 175, 0,
    215, 175, 95,
    215, 175, 135,
    215, 175, 175,
    215, 175, 215,
    215, 175, 255,
    215, 215, 0,
    215, 215, 95,
    215, 215, 135,
    215, 215, 175,
    215, 215, 215,
    215, 215, 255,
    215, 255, 0,
    215, 255, 95,
    215, 255, 135,
    215, 255, 175,
    215, 255, 215,
    215, 255, 255,
    255, 0, 0,
    255, 0, 95,
    255, 0, 135,
    255, 0, 175,
    255, 0, 215,
    255, 0, 255,
    255, 95, 0,
    255, 95, 95,
    255, 95, 135,
    255, 95, 175,
    255, 95, 215,
    255, 95, 255,
    255, 135, 0,
    255, 135, 95,
    255, 135, 135,
    255, 135, 175,
    255, 135, 215,
    255, 135, 255,
    255, 175, 0,
    255, 175, 95,
    255, 175, 135,
    255, 175, 175,
    255, 175, 215,
    255, 175, 255,
    255, 215, 0,
    255, 215, 95,
    255, 215, 135,
    255, 215, 175,
    255, 215, 215,
    255, 215, 255,
    255, 255, 0,
    255, 255, 95,
    255, 255, 135,
    255, 255, 175,
    255, 255, 215,
    255, 255, 255,
    8, 8, 8,
    18, 18, 18,
    28, 28, 28,
    38, 38, 38,
    48, 48, 48,
    58, 58, 58,
    68, 68, 68,
    78, 78, 78,
    88, 88, 88,
    98, 98, 98,
    108, 108, 108,
    118, 118, 118,
    128, 128, 128,
    138, 138, 138,
    148, 148, 148,
    158, 158, 158,
    168, 168, 168,
    178, 178, 178,
    188, 188, 188,
    198, 198, 198,
    208, 208, 208,
    218, 218, 218,
    228, 228, 228,
    238, 238, 238,
)  # fmt: skip
