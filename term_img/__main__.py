"""Support for command-line execution using `python -m term-img`"""

import logging as _logging
import multiprocessing
import sys
from threading import Event
from time import sleep

from .exit_codes import FAILURE, INTERRUPTED, codes


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
        if logging.QUIET:
            return
        notify.end_loading()
        if not main.loop:  # TUI not yet launched
            while notify.is_loading():
                pass
            notify.end_loading()
        notify.loading_indicator.join()

    def finish_multi_logging():
        if logging.MULTI:
            from multiprocessing import active_children

            from .logging_multi import log_queue, pids

            if log_queue:  # Multi-logging has been successfully initialized
                while pids.intersection({proc.pid for proc in active_children()}):
                    sleep(0.005)
                log_queue.put((None,) * 2)  # End of logs
                log_queue.join()

    # Can't use "term_img", since the logger's level is changed.
    # Otherwise, it would affect children of "term_img".
    logger = _logging.getLogger("term-img")
    logger.setLevel(_logging.INFO)

    cli.interrupted = main.interrupted = Event()
    try:
        exit_code = cli.main()
    except KeyboardInterrupt:
        cli.interrupted.set()  # Signal interruption to other threads.
        finish_loading()
        finish_multi_logging()
        logging.log(
            "Session interrupted",
            logger,
            _logging.CRITICAL,
            # If logging has been successfully initialized
            file=logging.VERBOSE is not None,
            # If the TUI was not launched, only print to console if verbosity is enabled
            direct=bool(main.loop or cli.args.verbose or cli.args.debug),
        )
        if cli.args.debug:
            raise
        return INTERRUPTED
    except Exception as e:
        cli.interrupted.set()  # Signal interruption to other threads.
        finish_loading()
        finish_multi_logging()
        logger.exception("Session terminated due to:")
        logging.log(
            f"Session not ended successfully: ({type(e).__name__}) {e}",
            logger,
            _logging.CRITICAL,
            # If logging has been successfully initialized
            file=logging.VERBOSE is not None,
        )
        if cli.args.debug:
            raise
        return FAILURE
    else:
        finish_loading()
        finish_multi_logging()
        logger.info(f"Session ended with return-code {exit_code} ({codes[exit_code]})")
        return exit_code
    finally:
        # Explicit cleanup is neccessary since the top-level `Image` widgets
        # (and by implication, `TermImage` instances) will probably still have
        # references to them hidden deep somewhere :)
        if cli.url_images is not None:
            for _, value in cli.url_images:
                value._image.close()


if __name__ == "__main__":
    sys.exit(main())
