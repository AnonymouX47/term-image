"""Support for command-line execution using `python -m term-img`"""

import logging
import sys

from .exit_codes import codes, FAILURE, INTERRUPTED
from . import cli

if __name__ == "__main__":
    from .logging import log

    # Can't use "term_img", since the logger's level is changed.
    # Otherwise, it would affect children of "term_img".
    logger = logging.getLogger("term-img")

    try:
        exit_code = cli.main()
    except KeyboardInterrupt:
        log("Session interrupted", logger, logging.INFO)
        if cli.args.debug:
            raise
        sys.exit(INTERRUPTED)
    except Exception as e:
        log(
            f"Session not ended successfully: ({type(e).__name__}) {e}",
            logger,
            logging.CRITICAL,
        )
        if cli.args.debug:
            raise
        sys.exit(FAILURE)
    else:
        logger.info(f"Session ended with return-code {exit_code} ({codes[exit_code]})")
        sys.exit(exit_code)
