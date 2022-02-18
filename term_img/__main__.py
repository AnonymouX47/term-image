"""Support for command-line execution using `python -m term-img`"""

import logging as _logging
import multiprocessing
import sys

from .exit_codes import FAILURE, INTERRUPTED, codes


def main() -> int:
    """CLI execution entry-point"""
    from .config import init_config

    # 1. `PIL.Image.open()` seems to cause forked child processes to block when called
    # in both the parent and the child.
    # 2. Unifies thing across multiple platforms, since Windows doesn't support
    # `os.fork()`.
    multiprocessing.set_start_method("spawn")

    init_config()  # Must be called before anything else is imported from `.config`.

    # Delay loading of other modules till after user-config is loaded
    from . import cli, logging, notify
    from .tui import main

    # Can't use "term_img", since the logger's level is changed.
    # Otherwise, it would affect children of "term_img".
    logger = _logging.getLogger("term-img")
    logger.setLevel(_logging.INFO)

    try:
        exit_code = cli.main()
    except KeyboardInterrupt:
        notify.stop_loading()  # Ensure loading stops, if ongoing.
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
        notify.stop_loading()  # Ensure loading stops, if ongoing.
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
