"""Issuing user notifications in the TUI and on STDOUT"""

from queue import Queue
from threading import Thread
from time import sleep
from typing import Any, Union, Tuple

import urwid

from .tui import main
from .tui import widgets
from . import logging
from . import tui

DEBUG = INFO = 0
WARNING = 1
ERROR = 2
CRITICAL = 3


def add_notification(msg: Union[str, Tuple[str, str]]) -> None:
    """Adds a message to the TUI notification bar"""
    if _alarms.qsize() == MAX_NOTIFICATIONS:
        clear_notification(main.loop, None)
    widgets.notifications.contents.insert(
        0, (urwid.Filler(urwid.Text(msg, wrap="ellipsis")), ("given", 1))
    )
    _alarms.put(main.loop.set_alarm_in(5, clear_notification))


def clear_notification(
    loop: Union[urwid.MainLoop, urwid.main_loop.EventLoop], data: Any
) -> None:
    """Removes the oldest message in the TUI notification bar"""
    widgets.notifications.contents.pop()
    loop.remove_alarm(_alarms.get())


def load(stopped: list[bool]) -> None:
    """Displays an elipsis-style loading indicator on STDOUT"""
    while not stopped[0]:
        for stage in (".  ", ".. ", "..."):
            print(stage, end="")
            print("\b" * 3, end="", flush=True)
            sleep(0.25)


def notify(
    msg: str, *, verbose: bool = False, level: int = INFO, loading: bool = False
) -> None:
    """Displays a message in the TUI's notification bar or on STDOUT"""
    if verbose and not logging.VERBOSE:
        pass
    elif not tui.is_launched:
        print(f"\033[31m{msg}\033[0m" if level >= ERROR else msg)
        if loading:
            start_loading()
    else:
        # CRITICAL-level notifications should never be displayed in the TUI,
        # since the program shouldn't recover from the cause.
        add_notification((msg, ("warning", msg), ("error", msg))[level])


def start_loading() -> None:
    """Starts a thread to display a loading indicator on STDOUT"""
    global _loading_thread

    stop_loading()  # Ensure previous loading has stopped, if any.
    _loading_stopped[0] = False
    _loading_thread = Thread(target=load, args=(_loading_stopped,))
    _loading_thread.start()


def stop_loading() -> None:
    """Stops the thread displaying a loading indicator on STDOUT"""
    global _loading_thread

    if not _loading_stopped[0]:
        _loading_stopped[0] = True
        _loading_thread.join()
        _loading_thread = None


MAX_NOTIFICATIONS = 2
_alarms = Queue(MAX_NOTIFICATIONS)
_loading_thread = None
_loading_stopped = [True]
