from __future__ import annotations

__all__ = (
    "no_redecorate",
    "color",
)

from functools import wraps
from types import FunctionType
from typing import Callable

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
