"""Extension of `.logging` for multiprocessing support"""

from __future__ import annotations

import logging as _logging
import os
from multiprocessing import JoinableQueue, Process
from traceback import format_exception

import term_image

from . import FontRatio, cli, logging, notify, set_font_ratio, tui


def process_multi_logs() -> None:
    """Emits logs and notifications redirected from subprocesses.

    Intended to be executed in a separate thread of the main process.
    """
    global log_queue

    PID = os.getpid()
    log_queue = JoinableQueue()
    process_multi_logs.started.set()

    log_type, data = log_queue.get()
    while data:
        if log_type == LOG:
            data["process"] = PID
            _logger.handle(_logging.makeLogRecord(data))
        else:
            notify.notify(*data[0], **data[1])
        log_queue.task_done()
        log_type, data = log_queue.get()
    log_queue.task_done()


class Process(Process):
    """A process with integration into the logging system

    Sets up the logging system to redirect all logs (and optionally notifcations)
    in the subprocess, to the main process to be emitted.

    NOTE:
        - Only TUI notifications need to be redirected.
        - The redirected logs and notifcations are automatically handled by
          `process_multi_logs()`, running in the MultiLogger thread of the main process.
    """

    def __init__(self, *args, redirect_notifs: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._log_queue = log_queue
        self._logging_details = {
            "constants": {
                name: value for name, value in vars(logging).items() if name.isupper()
            },
            "logging_level": _logging.getLogger().getEffectiveLevel(),
            "redirect_notifs": redirect_notifs,
        }
        self._main_process_interrupted = cli.interrupted
        self._font_ratio = cli.args.font_ratio
        self._query_timeout = term_image.utils.QUERY_TIMEOUT
        self._swap_win_size = term_image.utils.SWAP_WIN_SIZE
        self._ImageClass = tui.main.ImageClass
        exported_attrs = exported_style_attrs.get(cli.args.style)
        if self._ImageClass and exported_attrs:
            self._style_attrs = {
                item
                for item in vars(tui.main.ImageClass).items()
                if item[0] in exported_attrs
            }
        child_processes.append(self)

    def run(self):
        self._redirect_logs()
        _logger.debug("Starting")

        try:
            term_image.utils.QUERY_TIMEOUT = self._query_timeout
            term_image.utils.SWAP_WIN_SIZE = self._swap_win_size

            if self._ImageClass:
                # The unpickled class object is in the originally defined state
                # Eliminates queries for style support checks
                self._ImageClass._supported = True
                if self._ImageClass.__name__[:-5].lower() in exported_style_attrs:
                    for item in self._style_attrs:
                        setattr(self._ImageClass, *item)

            if not self._font_ratio:
                # Avoid error in case the terminal would not respond on time
                term_image._auto_font_ratio = True
            set_font_ratio(self._font_ratio or FontRatio.FULL_AUTO)

            super().run()
        except KeyboardInterrupt:
            # Log only if the main process was not interrupted
            if not self._main_process_interrupted.wait(0.1):
                logging.log(
                    "Interrupted" if logging.DEBUG else f"{self.name} was interrupted",
                    _logger,
                    _logging.ERROR,
                    direct=False,
                )
        except Exception:
            logging.log_exception(
                "Aborted" if logging.DEBUG else f"{self.name} was aborted", _logger
            )
        else:
            _logger.debug("Exiting")

    def _notif_redirector(self, *args, loading: bool = False, **kwargs):
        self._log_queue.put((NOTIF, (args, kwargs)))

    def _redirect_logs(self) -> None:
        # Logs
        vars(logging).update(self._logging_details["constants"])
        logger = _logging.getLogger()
        logger.setLevel(self._logging_details["logging_level"])
        logger.addHandler(RedirectHandler(self._log_queue))
        logger.handlers[0].addFilter(logging.filter_)

        # # Warnings and session-level logs
        _logger.setLevel(min(self._logging_details["logging_level"], _logging.INFO))

        # Notifications
        if self._logging_details["redirect_notifs"] and not logging.QUIET:
            notify.notify = self._notif_redirector


class RedirectHandler(_logging.Handler):
    """Puts the attribute dict of log records into *log_queue*.

    The records can be recreated with `logging.makeLogRecord()` and emitted with the
    `handle()` method of a logger with a different handler.
    """

    def __init__(self, log_queue: JoinableQueue, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._log_queue = log_queue

    def handle(self, record: _logging.LogRecord):
        attrdict = vars(record)
        exc_info = attrdict["exc_info"]
        if exc_info:
            # traceback objects cannot be pickled
            attrdict["msg"] = "\n".join(
                (attrdict["msg"], "".join(format_exception(*exc_info)))
            ).rstrip()
            attrdict["exc_info"] = None
        self._log_queue.put((LOG, attrdict))


_logger = _logging.getLogger("term-image")

LOG = 0
NOTIF = 1
child_processes = []
exported_style_attrs = {
    "iterm2": {"_TERM", "_TERM_VERSION"},
    "kitty": {"_KITTY_VERSION", "_KONSOLE_VERSION"},
}

# The annotations below are put in comments for compatibility with Python 3.7
# as it doesn't allow names declared as `global` within functions to be annotated.

# Set from `process_multi_logs()` in the MultiLogger thread, only in the main process
log_queue = None  #: Optional[JoinableQueue]
