"""Extension of `.logging` for multiprocessing support"""

# Helps to avoid circular imports when the LogManager server process is starting

import logging as _logging
import os
from multiprocessing.managers import BaseManager
from threading import Thread
from traceback import format_exception


def create_queue():
    from queue import Queue

    global _log_queue
    _log_queue = Queue()


def get_log_queue():
    return _log_queue


def get_logging_details():
    return _logging_details


def redirect_logs(logger: _logging.Logger) -> None:
    """Sets up the logging system to redirect records produced by *logger* in a
    sub-process to the main process.

    Args:
        logger: The `logging.Logger` instance of the module from which this function is
          called.

    NOTE:
        - The function is meant to be called from within the sub-process,
        - The redirected records are automatically handled by the "MultiLogger" thread
          of the main process, running `process_logs()`.
    """
    from . import logging

    def log_redirector(record):
        attrdict = record.__dict__
        exc_info = attrdict["exc_info"]
        if exc_info:
            # traceback objects cannot be pickled
            attrdict["msg"] = "\n".join(
                (attrdict["msg"], "".join(format_exception(*exc_info)))
            ).rstrip()
            attrdict["exc_info"] = None
        log_queue.put(attrdict)

    LogManager.register("get_logging_details")
    LogManager.register("get_log_queue")
    log_manager = LogManager(("", 54321))
    log_manager.connect()

    # Ensure details have been uploaded by MultiLogger
    while not log_manager.get_logging_details()._getvalue():
        pass

    logging_level, constants = log_manager.get_logging_details()._getvalue()
    log_queue = log_manager.get_log_queue()

    logging.__dict__.update(constants)
    logger.setLevel(logging_level)
    logger.filter = log_redirector


def process_multi_logs() -> None:
    """Emits logs redirected from sub-processes.

    Intended to be executed in a separate thread of the main process.
    """
    from . import logging

    LogManager.register("get_logging_details", get_logging_details)
    LogManager.register("get_log_queue", get_log_queue)
    log_manager = LogManager(("", 54321))
    log_manager.start(create_queue)

    log_manager.get_logging_details().extend(
        [
            _logging.getLogger().getEffectiveLevel(),
            # Constants defined in `.logging`
            {name: value for name, value in logging.__dict__.items() if name.isupper()},
        ]
    )

    PID = os.getpid()
    # _log_queue is used in `.__main__.main()`.
    globals()["_log_queue"] = log_queue = log_manager.get_log_queue()

    attrdict = log_queue.get()
    while attrdict:
        attrdict["process"] = PID
        _logger.handle(_logging.makeLogRecord(attrdict))
        attrdict = log_queue.get()


class LogManager(BaseManager):
    pass


multi_logger = Thread(target=process_multi_logs, name="MultiLogger")

_logger = _logging.getLogger("term-img")
_log_queue = None
_logging_details = []
