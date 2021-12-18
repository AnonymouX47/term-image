"""Event logging"""

import logging
import os
import sys
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
    level: int = logging.INFO,
    *,
    direct: bool = True,
    file: bool = True,
    verbose: bool = False,
):
    """Report events to various destinations"""

    if verbose:
        if VERBOSE:
            logger.log(level, msg, stacklevel=2)
            (
                info_bar.original_widget.set_text(
                    ("error", msg) if level == logging.ERROR else msg
                )
                if tui.launched
                else print(f"\033[31m{msg}\033[0m" if level >= logging.ERROR else msg)
            )
        elif VERBOSE_LOG:
            logger.log(level, msg, stacklevel=2)
    else:
        if file:
            logger.log(level, msg, stacklevel=2)
        if direct:
            (
                info_bar.original_widget.set_text(
                    ("error", msg) if level == logging.ERROR else msg
                )
                if tui.launched
                else print(f"\033[31m{msg}\033[0m" if level >= logging.ERROR else msg)
            )


def log_exception(msg: str, logger: logging.Logger, *, direct=False) -> None:
    """Report an error with the exception reponsible
    
    NOTE: Should be called from within an exception handler
    i.e from (also possibly in a nested context) within an except or finally clause.
    """
    if DEBUG:
        logger.exception(f"{msg} due to:", stacklevel=3)
    elif VERBOSE or VERBOSE_LOG:
        exc_type, exc, _ = sys.exc_info()
        logger.error(f"{msg} due to: ({exc_type.__name__}) {exc}", stacklevel=3)
    else:
        logger.error(msg, stacklevel=3)

    if direct:
        (
            info_bar.original_widget.set_text(("error", msg))
            if tui.launched
            else print(f"\033[31m{msg}\033[0m")
        )


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
