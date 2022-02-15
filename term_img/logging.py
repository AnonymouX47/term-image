"""Event logging"""

import logging
import os
import sys
import warnings
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from typing import Optional, Set

from . import notify


def init_log(
    logfile: str,
    level: int,
    debug: bool,
    verbose: bool = False,
    verbose_log: bool = False,
) -> None:
    """Initialize application event logging"""
    global DEBUG, VERBOSE, VERBOSE_LOG

    handler = RotatingFileHandler(
        logfile,
        maxBytes=2 ** 20,  # 1 MiB
        backupCount=1,
    )
    handler.addFilter(filter_)

    VERBOSE, VERBOSE_LOG = verbose or debug, verbose_log
    DEBUG = debug = debug or level == logging.DEBUG
    if debug:
        level = logging.DEBUG
    elif VERBOSE or VERBOSE_LOG:
        level = logging.INFO

    FORMAT = (
        "({instance_id}) ({asctime}) "
        + "{processName}: {threadName}: " * debug
        + "[{levelname}] {name}: "
        + "{funcName}: " * (debug and stacklevel_is_available)
        + "{message}"
    )
    logging.basicConfig(
        handlers=(handler,),
        format=FORMAT,
        datefmt="%d-%m-%Y %H:%M:%S",
        style="{",
        level=level,
    )

    logger.info("Starting a new session")
    logger.info(f"Logging level set to {logging.getLevelName(level)}")

    if debug and not stacklevel_is_available:
        warnings.warn(
            "Please upgrade to Python 3.8 or later to get more detailed logs."
        )


def _log(*args, _extra={"instance_id": os.getpid()}, **kwargs):
    """Ensures child processes record the PID of the main process"""
    return _ori_log(*args, **kwargs, extra=_extra)


def log(
    msg: str,
    logger: Optional[logging.Logger] = None,
    level: int = logging.INFO,
    *,
    direct: bool = True,
    file: bool = True,
    verbose: bool = False,
    loading: bool = False,
) -> None:
    """Report events to various destinations"""
    if loading:
        msg += "..."
    # > log > _log > _ori_log
    kwargs = {"stacklevel": 3} if stacklevel_is_available else {}

    if verbose:
        if VERBOSE:
            logger.log(level, msg, **kwargs)
            notify.notify(
                msg, level=getattr(notify, logging.getLevelName(level)), loading=loading
            )
        elif VERBOSE_LOG:
            logger.log(level, msg, **kwargs)
    else:
        if file:
            logger.log(level, msg, **kwargs)
        if direct:
            notify.notify(
                msg, level=getattr(notify, logging.getLevelName(level)), loading=loading
            )


def log_exception(msg: str, logger: logging.Logger, *, direct: bool = False) -> None:
    """Report an error with the exception reponsible

    NOTE: Should be called from within an exception handler
    i.e from (also possibly in a nested context) within an except or finally clause.
    """
    # > exception-handler > log_exception > _log > _ori_log
    kwargs = {"stacklevel": 4} if stacklevel_is_available else {}

    if DEBUG:
        logger.exception(f"{msg} due to:", **kwargs)
    elif VERBOSE or VERBOSE_LOG:
        exc_type, exc, _ = sys.exc_info()
        logger.error(f"{msg} due to: ({exc_type.__name__}) {exc}", **kwargs)
    else:
        logger.error(msg, **kwargs)

    if VERBOSE and direct:
        notify.notify(msg, level=notify.ERROR)


# Not annotated because it's not directly used.
def log_warning(msg, catg, fname, lineno, f=None, line=None):
    logger.warning(warnings.formatwarning(msg, catg, fname, lineno, line))
    notify.notify(
        "Please view the logs for some warning(s).",
        level=notify.WARNING,
    )


# See "Filters" section in `logging` standard library documentation.
@dataclass
class Filter:
    disallowed: Set[str]

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.partition(".")[0] not in self.disallowed

    def add(self, name: str) -> None:
        self.disallowed.add(name)

    def remove(self, name: str) -> None:
        self.disallowed.remove(name)


filter_ = Filter({"PIL", "urllib3"})

# Writing to STDERR messes up output, especially with the TUI
warnings.showwarning = log_warning

# To ensure child processes record the same PID as the main process
_ori_log = logging.Logger._log
logging.Logger._log = _log

# Can't use "term_img", since the logger's level is changed in `.__main__`.
# Otherwise, it would affect children of "term_img".
logger = logging.getLogger("term-img")

# the _stacklevel_ parameter was added in Python 3.8
stacklevel_is_available = sys.version_info[:3] >= (3, 8, 0)

# Set from within `init_log()`
DEBUG = None
VERBOSE = None
VERBOSE_LOG = None
