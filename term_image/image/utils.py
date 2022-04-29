from __future__ import annotations

from typing import Tuple

_BG_FMT = "\033[48;2;%d;%d;%dm"
_FG_FMT = "\033[38;2;%d;%d;%dm"
_RESET = "\033[0m"


def _color(
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
