"""Event logging"""

import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from typing import List, Optional

from .tui.config import user_dir
from .tui.widgets import info_bar
from . import tui


def init_log(level: int, debug: bool, verbose: bool = False, verbose_log: bool = False):
    """Initialize application event logging"""
    global DEBUG, VERBOSE, VERBOSE_LOG

    VERBOSE, VERBOSE_LOG = verbose or debug, verbose_log

    handler = RotatingFileHandler(
        os.path.join(user_dir, "term_img.log"),
        maxBytes=2 ** 20,  # 1 MiB
        backupCount=1,
    )
    handler.addFilter(_filter)

    DEBUG = debug = debug or level == logging.DEBUG
    if debug:
        level = logging.DEBUG
    elif VERBOSE or VERBOSE_LOG:
        level = logging.INFO

    FORMAT = (
        "({process}) "
        + "({asctime}) " * debug
        + "[{levelname}] {name}: "
        + "{funcName}: " * debug
        + "{message}"
    )
    logging.basicConfig(
        handlers=(handler,),
        format=FORMAT,
        datefmt="%d-%m-%Y %H:%M:%S",
        style="{",
        level=level,
    )

    # Can't use "term_img", since the logger's level is changed in `__main__.py`.
    # Otherwise, it would affect children of "term_img".
    logger = logging.getLogger("term-img")
    logger.setLevel(logging.INFO)
    logger.info("Starting a new session")
    logger.info(f"Logging level set to {logging.getLevelName(level)}")


def log(
    msg: str,
    logger: Optional[logging.Logger] = None,
    level: Optional[int] = None,
    *,
    direct: bool = True,
    file: bool = True,
    verbose: bool = False,
    exc: Optional[Exception] = None,
):
    """Report events to various destinations"""

    if verbose:
        if VERBOSE:
            (
                log_exception(msg, exc, logger)
                if exc
                else logger.log(level, msg, stacklevel=2)
            )
            (info_bar.set_text if tui.launched else print)(msg)
        elif VERBOSE_LOG:
            (
                log_exception(msg, exc, logger)
                if exc
                else logger.log(level, msg, stacklevel=2)
            )
    else:
        if file:
            (
                log_exception(msg, exc, logger)
                if exc
                else logger.log(level, msg, stacklevel=2)
            )
        if direct:
            (info_bar.original_widget.set_text if tui.launched else print)(msg)


def log_exception(msg: str, exc: Exception, logger: logging.Logger) -> None:
    if DEBUG:
        logger.exception(f"{msg} due to:", stacklevel=4)
    elif VERBOSE or VERBOSE_LOG:
        logger.error(f"{msg} due to: ({type(exc).__name__}) {exc}", stacklevel=4)
    else:
        logger.error(msg, stacklevel=4)


@dataclass
class Filter:
    disallowed: List[str]

    def filter(self, record: logging.LogRecord):
        return not any(record.name.startswith(name) for name in self.disallowed)

    def add(self, name: str):
        self.disallowed.append(name)


_filter = Filter(["PIL"])

# Set from within `init_log()`
DEBUG = None
VERBOSE = None
VERBOSE_LOG = None
