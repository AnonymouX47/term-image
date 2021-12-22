"""Issuing user notifications in the TUI and on STDOUT"""

from queue import Queue
from typing import Any, Union, Tuple

import urwid

from .tui.widgets import notifications
from .tui import main
from . import logging
from . import tui

DEBUG = INFO = 0
WARNING = 1
ERROR = 2
CRITICAL = 3


def notify(msg: str, *, verbose: bool = False, level: int = INFO) -> None:
    """Display a message in the TUI's notification bar or the console"""
    if verbose and not logging.VERBOSE:
        return
    if not tui.launched:
        return print(f"\033[31m{msg}\033[0m" if level >= ERROR else msg)

    # CRITICAL-level notifications should never be displayed in the TUI,
    # since the program shouldn't recover from the cause.
    add_notification((msg, ("warning", msg), ("error", msg))[level])


def add_notification(msg: Union[str, Tuple[str, str]]) -> None:
    if _alarms.qsize() == MAX_NOTIFICATIONS:
        clear_notification(main.loop, None)
    notifications.contents.insert(
        0, (urwid.Filler(urwid.Text(msg, wrap="ellipsis")), ("given", 1))
    )
    _alarms.put(main.loop.set_alarm_in(5, clear_notification))


def clear_notification(
    loop: Union[urwid.MainLoop, urwid.main_loop.EventLoop], data: Any
) -> None:
    notifications.contents.pop()
    loop.remove_alarm(_alarms.get())


MAX_NOTIFICATIONS = 2
_alarms = Queue(MAX_NOTIFICATIONS)
