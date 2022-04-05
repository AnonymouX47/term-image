"""Extension of `.logging` for multiprocessing support"""

import logging as _logging
import os
from multiprocessing.managers import BaseManager


def create_objects():
    from queue import Queue

    global _log_queue, _logging_details
    _log_queue = Queue()
    _logging_details = []


def get_log_queue():
    return _log_queue


def get_logging_details():
    return _logging_details


def redirect_logs(*, notifs: bool = False) -> None:
    """Sets up the logging system to redirect all logs (and optionally notifcations)
    in a subprocess, to the main process to be emitted.

    Args:
        notifs: If `True`, notifications are redirected also.

    NOTE:
        - This function is meant to be called from within the subprocess.
        - Only TUI notifications need to be redirected.
        - The redirected records and notifcations are automatically handled by
          `process_logs()`, running in the MultiLogger thread of the main process.
    """
    from traceback import format_exception

    from . import logging, notify
    from .config import user_dir

    class RedirectHandler(_logging.Handler):
        def handle(self, record: _logging.LogRecord):
            attrdict = vars(record)
            exc_info = attrdict["exc_info"]
            if exc_info:
                # traceback objects cannot be pickled
                attrdict["msg"] = "\n".join(
                    (attrdict["msg"], "".join(format_exception(*exc_info)))
                ).rstrip()
                attrdict["exc_info"] = None
            log_queue.put((LOG, attrdict))

    def notif_redirector(*args, loading: bool = False, **kwargs):
        log_queue.put((NOTIF, (args, kwargs)))

    LogManager.register("get_logging_details")
    LogManager.register("get_log_queue")

    with open(os.path.join(user_dir, "temp", "addresses", str(os.getppid()))) as f:
        port = int(f.read())

    log_manager = LogManager(("127.0.0.1", port))
    log_manager.connect()

    logging_level, constants = log_manager.get_logging_details()._getvalue()
    log_queue = log_manager.get_log_queue()

    # Logs
    vars(logging).update(constants)

    handler = RedirectHandler()
    handler.addFilter(logging.filter_)

    logger = _logging.getLogger()
    logger.setLevel(logging_level)
    logger.addHandler(handler)

    # # Warnings and session-level logs
    _logger.setLevel(_logging.INFO)

    # Notifications
    if notifs and not logging.QUIET:
        notify.notify = notif_redirector


def process_multi_logs(log_manager: "LogManager") -> None:
    """Emits logs and notifications redirected from subprocesses.

    Intended to be executed in a separate thread of the main process.
    """
    from . import notify
    from .config import user_dir

    global log_queue

    PID = os.getpid()
    log_queue = log_manager.get_log_queue()

    log_type, data = log_queue.get()
    while data:
        if log_type == LOG:
            data["process"] = PID
            _logger.handle(_logging.makeLogRecord(data))
        else:
            args, kwargs = data
            notify.notify(*args, **kwargs)
        log_queue.task_done()
        log_type, data = log_queue.get()
    os.remove(os.path.join(user_dir, "temp", "addresses", str(PID)))
    log_queue.task_done()


class LogManager(BaseManager):
    pass


_logger = _logging.getLogger("term-img")

LOG = 0
NOTIF = 1

# Set from `process_multi_logs()` in the MultiLogger thread, only in the main process
log_queue = None

# Set from `create_objects()`, only in the manager process
_log_queue = None
_logging_details = None
