"""Issuing user notifications in the TUI and on STDOUT"""

import logging as _logging
from queue import Queue
from sys import stderr, stdout
from threading import Event, Thread
from time import sleep
from typing import Any, Tuple, Union

import urwid

from . import logging, tui
from .tui import main, widgets

DEBUG = INFO = 0
WARNING = 1
ERROR = 2
CRITICAL = 3


def add_notification(msg: Union[str, Tuple[str, str]]) -> None:
    """Adds a message to the TUI notification bar."""
    if _alarms.qsize() == MAX_NOTIFICATIONS:
        clear_notification(main.loop, None)
    widgets.notifications.contents.insert(
        0, (urwid.Filler(urwid.Text(msg, wrap="ellipsis")), ("given", 1))
    )
    _alarms.put(main.loop.set_alarm_in(5, clear_notification))


def clear_notification(
    loop: Union[urwid.MainLoop, urwid.main_loop.EventLoop], data: Any
) -> None:
    """Removes the oldest message in the TUI notification bar."""
    widgets.notifications.contents.pop()
    loop.remove_alarm(_alarms.get())


def end_loading() -> None:
    """Signals the end of all progressive operations for the current mode."""
    global _n_loading

    _n_loading = -1
    _loading.set()


def is_loading() -> bool:
    """Returns ``True`` if the loading indicator is active or ``False`` if not."""
    return _loading.is_set()


def load() -> None:
    """Displays a loading indicator.

    - elipsis-style for the CLI
    - braille-style for the TUI
    """
    from .tui.main import update_screen
    from .tui.widgets import loading

    global _n_loading

    _loading.wait()
    logger.debug("Starting")

    while _n_loading > -1:
        while _n_loading > 0:
            for stage in (".  ", ".. ", "..."):
                print(stage + "\b" * 3, end="", flush=True)
                if _n_loading <= 0:
                    break
                sleep(0.25)
        print(" " * 3 + "\b" * 3, end="", flush=True)
        if _n_loading > -1:
            _loading.clear()
            _loading.wait()

    _n_loading = 0
    _loading.clear()
    _loading.wait()

    while _n_loading > -1:
        while _n_loading > 0:
            for stage in (
                "\u28bf",
                "\u28fb",
                "\u28fd",
                "\u28fe",
                "\u28f7",
                "\u28ef",
                "\u28df",
                "\u287f",
            ):
                loading.set_text(stage)
                update_screen()
                if _n_loading <= 0:
                    break
                sleep(0.25)
        loading.set_text("")
        update_screen()
        if _n_loading > -1:
            _loading.clear()
            _loading.wait()

    logger.debug("Exiting")


def notify(
    msg: str, *, verbose: bool = False, level: int = INFO, loading: bool = False
) -> None:
    """Displays a message in the TUI's notification bar or on STDOUT."""
    if logging.QUIET and level < CRITICAL or verbose and not logging.VERBOSE:
        return

    if not tui.is_launched:
        print(
            (
                f"\033[33m{msg}\033[0m"
                if level == WARNING
                else f"\033[31m{msg}\033[0m"
                if level >= ERROR
                else msg
            ),
            file=stderr if level >= ERROR else stdout,
        )
        if loading:
            start_loading()
    else:
        # CRITICAL-level notifications should never be displayed in the TUI,
        # since the program shouldn't recover from the cause.
        add_notification((msg, ("warning", msg), ("error", msg))[level])


def start_loading() -> None:
    """Signals the start of a progressive operation."""
    global _n_loading

    _n_loading += 1
    _loading.set()


def stop_loading() -> None:
    """Signals the end of a progressive operation."""
    global _n_loading

    _n_loading -= 1


logger = _logging.getLogger(__name__)

MAX_NOTIFICATIONS = 2
_alarms = Queue(MAX_NOTIFICATIONS)

_loading = Event()
_n_loading = 0
loading_indicator = Thread(target=load, name="LoadingIndicator")
