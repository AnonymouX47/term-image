""".. Image widgets for TUI frameworks"""

from __future__ import annotations

__all__ = []

try:
    import urwid
except ImportError:
    pass
else:
    from .urwid import UrwidImage, UrwidImageCanvas, UrwidImageJanitor, UrwidImageScreen

    del urwid
    __all__ += [
        "UrwidImage",
        "UrwidImageCanvas",
        "UrwidImageJanitor",
        "UrwidImageScreen",
    ]
