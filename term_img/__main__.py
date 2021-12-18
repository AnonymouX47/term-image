"""Support for command-line execution using `python -m term-img`"""

import logging as _logging
import sys

from .exit_codes import codes, FAILURE, INTERRUPTED
from . import cli

if __name__ == "__main__":
    from . import logging

    # Can't use "term_img", since the logger's level is changed.
    # Otherwise, it would affect children of "term_img".
    logger = _logging.getLogger("term-img")

    try:
        exit_code = cli.main()
    except KeyboardInterrupt:
        logging.log(
            "Session interrupted",
            logger,
            _logging.CRITICAL,
            # If logging has been successfully initialized
            file=logging.VERBOSE is not None,
        )
        if cli.args.debug:
            raise
        sys.exit(INTERRUPTED)
    except Exception as e:
        logging.log(
            f"Session not ended successfully: ({type(e).__name__}) {e}",
            logger,
            _logging.CRITICAL,
            # If logging has been successfully initialized
            file=logging.VERBOSE is not None,
        )
        if cli.args.debug:
            raise
        sys.exit(FAILURE)
    else:
        logger.info(f"Session ended with return-code {exit_code} ({codes[exit_code]})")
        sys.exit(exit_code)
