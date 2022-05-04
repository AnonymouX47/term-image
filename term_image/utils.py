from __future__ import annotations

__all__ = (
    "OS_IS_UNIX",
    "no_redecorate",
    "cached",
    "lock_input",
    "unix_tty_only",
    "terminal_size_cached",
    "color",
    "read_input",
)

import os
import sys
import warnings
from functools import wraps
from multiprocessing import Process, RLock as mp_RLock
from shutil import get_terminal_size
from threading import RLock
from time import monotonic
from types import FunctionType
from typing import Callable, Optional, Tuple

# import logging

OS_IS_UNIX: bool
try:
    import fcntl  # noqa:F401
    import termios
    from select import select
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
def lock_input(func: Callable) -> FunctionType:
    """Enables global cooperative input synchronization on the decorated callable.

    When any decorated function is called, a re-entrant lock is acquired by the current
    process or thread and released after the call, such that any other decorated
    function called within another thread or subprocess has to wait till the lock is
    fully released (i.e has been released as many times as acquired) by the current
    process or thread.

    NOTE:
        It automatocally works across parent-/sub-processes (started with
        ``multiprocessing.Process``) and their threads.
        To achieve this, ``multiprocessing.Process`` is "hooked" and it works even with
        subclasses.

    IMPORTANT:
        It only works across processes started with ``multiprocessing.Process`` and
        if ``multiprocessing.synchronize`` is supported on the host platform.
        If not supported, a warning is issued when starting a subprocess.
    """

    @wraps(func)
    def lock_input_wrapper(*args, **kwargs):
        with _input_lock:
            # logging.debug(f"{func.__name__} acquired input lock", stacklevel=3)
            return func(*args, **kwargs)

    return lock_input_wrapper


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


@unix_tty_only
@lock_input
def read_input(
    more: Callable[[bytearray], bool] = lambda _: True,
    timeout: Optional[float] = None,
    min: int = 0,
    *,
    echo: bool = False,
) -> Optional[bytes]:
    """Reads input directly from the terminal with/without blocking.

    Args:
        more: A callable, which when passed the input recieved so far, returns a
          boolean indicating if the input is incomplete or not. If it returns:

          * ``True``, more input is waited for.
          * ``False``, the recieved input is returned immediately.

        timeout: Time limit for awaiting input, in seconds.
        min: Causes to block until at least the given number of bytes have been read.
        echo: If ``True``, any input while waiting is printed unto the screen.
          Any input before or after calling this function is not affected.

    If *timeout* is ``None`` (default), all available input is read without blocking.

    If *timeout* is not ``None`` and:

      * *min* > ``0``, input is waited for until at least *min* bytes have been read.

        After *min* bytes have been read, the following points apply with *timeout*
        being the leftover of the original *timeout*, if not yet used up.

      * *more* is not given, input is read or waited for until *timeout* is up.
      * *more* is given, input is read or waited for until ``more(input)`` returns
        ``False`` or *timeout* is up.

    If *min* == ``0`` (default) and no input is recieved, ``None`` is returned.

    Upon return or interruption, the terminal is **immediately** restored to the
    state in which it was met.
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

        if timeout is None:
            chunk = os.read(_tty, 100)
            while chunk:
                input.extend(chunk)
                chunk = os.read(_tty, 100)
        else:
            start = monotonic()

            if min > 0:
                input.extend(os.read(_tty, min))

                # Don't block based on based on amount of bytes anymore
                new_attr[6][termios.VMIN] = 0
                termios.tcsetattr(_tty, termios.TCSANOW, new_attr)

            r, w, x = [_tty], [], []
            while monotonic() - start < timeout and more(input):
                # Using select reduces CPU usage
                if select(r, w, x, timeout - (monotonic() - start))[0]:
                    input.extend(os.read(_tty, 1))
            # logging.debug(f"{monotonic() - start}")
    finally:
        termios.tcsetattr(_tty, termios.TCSANOW, old_attr)

    return bytes(input) if input else None


def _process_start_wrapper(self, *args, **kwargs):
    global _input_lock

    if isinstance(_input_lock, type(RLock())):
        try:
            # Ensure it's not acquired by another process/thread before changing it.
            # The only way this can be countered is if the owner process/thread is the
            # one starting a process, which is very unlikely within a function meant
            # for input :|
            with _input_lock:
                self._input_lock = _input_lock = mp_RLock()
        except ImportError:
            self._input_lock = None
            warnings.warn(
                "Multi-process synchronization is not supported on this platform! "
                "Hence, if any subprocess will be reading from STDIN, "
                "it will be unsafe to use any image render style based on a terminal "
                "graphics protocol or to use automatic font ratio.\n"
                "You can simply set an 'ignore' filter for this warning if not using "
                "any of the features affected.",
                UserWarning,
            )
    else:
        self._input_lock = _input_lock

    return _process_start_wrapper.__wrapped__(self, *args, **kwargs)


def _process_run_wrapper(self, *args, **kwargs):
    global _input_lock

    if self._input_lock:
        _input_lock = self._input_lock
    return _process_run_wrapper.__wrapped__(self, *args, **kwargs)


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

        _input_lock = RLock()

        Process.start = wraps(Process.start)(_process_start_wrapper)
        Process.run = wraps(Process.run)(_process_run_wrapper)

        # Shouldn't be needed since we're getting our own separate file descriptors
        # but the validity of the assumed safety is stil under probation
        """
        for name, value in vars(termios).items():
            if isinstance(value, BuiltinFunctionType):
                setattr(termios, name, lock_input(value))
        """
