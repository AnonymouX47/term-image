"""Event logging"""

import logging
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
    no_multi: bool,
    verbose: bool = False,
    verbose_log: bool = False,
) -> None:
    """Initialize application event logging"""
    global DEBUG, MULTI, VERBOSE, VERBOSE_LOG

    handler = RotatingFileHandler(
        logfile,
        maxBytes=2**20,  # 1 MiB
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
        "({process}) ({asctime}) "
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

    _logger.info("Starting a new session")
    _logger.info(f"Logging level set to {logging.getLevelName(level)}")

    if debug and not stacklevel_is_available:
        warnings.warn(
            "Please upgrade to Python 3.8 or later to get more detailed logs."
        )

    try:
        import multiprocessing.synchronize  # noqa: F401
    except ImportError:
        MULTI = False
    else:
        MULTI = not no_multi

    if MULTI:
        import os
        from errno import errorcode
        from multiprocessing.connection import Listener
        from random import randint
        from threading import Thread

        from . import logging_multi
        from .config import user_dir
        from .logging_multi import LogManager, create_objects, process_multi_logs

        for name, value in vars(logging_multi).items():
            if name.startswith("get_"):
                LogManager.register(name, value)

        # Get a port that's not in use
        # Allows multiple sessions of `term-img` on the same machine at the same time
        init_err_msg = (
            "Unable to initialize the multi-process logging system..."
            " Disabling multiprocessing!"
        )
        errors = 0
        while True:
            port = randint(50000, 60000)
            try:
                with Listener(("127.0.0.1", 0)):
                    pass
            except OSError as e:
                if not errorcode[e.errno].endswith("EADDRINUSE"):
                    errors += 1
                    # Try 3 times before concluding the error is fatal
                    if errors == 3:
                        log_exception(init_err_msg, _logger, direct=True)
                        MULTI = False
                        return
            except Exception:
                log_exception(init_err_msg, _logger, direct=True)
                MULTI = False
                return
            else:
                break

        address_dir = os.path.join(user_dir, "temp", "addresses")
        os.makedirs(address_dir, exist_ok=True)
        with open(os.path.join(address_dir, str(os.getpid())), "w") as f:
            f.write(str(port))

        log_manager = LogManager(("127.0.0.1", port))
        log_manager.start(create_objects)
        log_manager.get_logging_details().extend(
            [
                logging.getLogger().getEffectiveLevel(),
                # Constants defined in this module
                {name: value for name, value in globals().items() if name.isupper()},
            ]
        )

        Thread(
            target=process_multi_logs, args=(log_manager,), name="MultiLogger"
        ).start()

        while not logging_multi.log_queue:  # Wait till MultiLogger has started
            pass

        _logger.debug("Successfully initialized the multi-process logging system.")


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

    if verbose:
        if VERBOSE:
            logger.log(level, msg, **_kwargs)
            notify.notify(
                msg, level=getattr(notify, logging.getLevelName(level)), loading=loading
            )
        elif VERBOSE_LOG:
            logger.log(level, msg, **_kwargs)
    else:
        if file:
            logger.log(level, msg, **_kwargs)
        if direct:
            notify.notify(
                msg, level=getattr(notify, logging.getLevelName(level)), loading=loading
            )


def log_exception(msg: str, logger: logging.Logger, *, direct: bool = False) -> None:
    """Report an error with the exception reponsible

    NOTE: Should be called from within an exception handler
    i.e from (also possibly in a nested context) within an except or finally clause.
    """
    if DEBUG:
        logger.exception(f"{msg} due to:", **_kwargs_exc)
    elif VERBOSE or VERBOSE_LOG:
        exc_type, exc, _ = sys.exc_info()
        logger.error(f"{msg} due to: ({exc_type.__name__}) {exc}", **_kwargs)
    else:
        logger.error(msg, **_kwargs)

    if VERBOSE and direct:
        notify.notify(msg, level=notify.ERROR)


# Not annotated because it's not directly used.
def _log_warning(msg, catg, fname, lineno, f=None, line=None):
    """Redirects warnings to the logging system.

    Intended to replace `warnings.showwarning()`.
    """
    _logger.warning(warnings.formatwarning(msg, catg, fname, lineno, line))
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
warnings.showwarning = _log_warning

# Can't use "term_img", since the logger's level is changed in `.__main__`.
# Otherwise, it would affect children of "term_img".
_logger = logging.getLogger("term-img")

# the _stacklevel_ parameter was added in Python 3.8
stacklevel_is_available = sys.version_info[:3] >= (3, 8, 0)
if stacklevel_is_available:
    # > log > logger.log > _log
    _kwargs = {"stacklevel": 2}
    # > exception-handler > log_exception > logger.exception > _log
    _kwargs_exc = {"stacklevel": 3}
else:
    _kwargs = _kwargs_exc = {}

# Set from within `init_log()`
DEBUG = None
MULTI = None
VERBOSE = None
VERBOSE_LOG = None
