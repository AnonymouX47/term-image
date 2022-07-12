"""Support for command-line execution using `python -m term-image`"""

from __future__ import annotations

import logging as _logging
import multiprocessing
import sys
from threading import Event

from .exit_codes import FAILURE, INTERRUPTED, codes
from .utils import write_tty


def main() -> int:
    """CLI execution entry-point"""
    from .config import init_config

    # 1. `PIL.Image.open()` seems to cause forked child processes to block when called
    # in both the parent and the child.
    # 2. Unifies things across multiple platforms.
    multiprocessing.set_start_method("spawn")

    init_config()  # Must be called before anything else is imported from `.config`.

    # Delay loading of other modules till after user-config is loaded
    from . import cli, logging, notify
    from .tui import main

    def finish_loading():
        if not logging.QUIET and notify.loading_indicator:
            notify.end_loading()
            if not main.loop:  # TUI was not launched
                while notify.is_loading():
                    pass
                notify.end_loading()
            notify.loading_indicator.join()

    def finish_multi_logging():
        if logging.MULTI:
            from .logging_multi import child_processes, log_queue

            if log_queue:  # Multi-logging has been successfully initialized
                for process in child_processes:
                    process.join()
                log_queue.put((None,) * 2)  # End of logs
                log_queue.join()

    # Can't use "term_image", since the logger's level is changed.
    # Otherwise, it would affect children of "term_image".
    logger = _logging.getLogger("term-image")
    logger.setLevel(_logging.INFO)

    cli.interrupted = Event()
    try:
        write_tty(b"\033[22;2t")  # Save window title
        write_tty(b"\033]2;Term-Image\033\\")  # Set window title
        exit_code = cli.main()
    except KeyboardInterrupt:
        cli.interrupted.set()  # Signal interruption to subprocesses and other threads.
        finish_loading()
        finish_multi_logging()
        logging.log(
            "Session interrupted",
            logger,
            _logging.CRITICAL,
            # If logging has been successfully initialized
            file=logging.VERBOSE is not None,
            # If the TUI was not launched, only print to console if verbosity is enabled
            direct=bool(main.loop or cli.args and (cli.args.verbose or cli.args.debug)),
        )
        if cli.args and cli.args.debug:
            raise
        return INTERRUPTED
    except Exception as e:
        cli.interrupted.set()  # Signal interruption to subprocesses and other threads.
        finish_loading()
        finish_multi_logging()
        logger.exception("Session terminated due to:")
        logging.log(
            "Session not ended successfully: "
            f"({type(e).__module__}.{type(e).__qualname__}) {e}",
            logger,
            _logging.CRITICAL,
            # If logging has been successfully initialized
            file=logging.VERBOSE is not None,
        )
        if cli.args and cli.args.debug:
            raise
        return FAILURE
    else:
        finish_loading()
        finish_multi_logging()
        logger.info(f"Session ended with return-code {exit_code} ({codes[exit_code]})")
        return exit_code
    finally:
        write_tty(b"\033[22;2t")  # Restore window title
        # Explicit cleanup is neccessary since the top-level `Image` widgets
        # will still hold references to the `BaseImage` instances
        if cli.url_images:
            for _, value in cli.url_images:
                value._ti_image.close()


if __name__ == "__main__":
    sys.exit(main())
