"""Support for command-line execution using `python -m term-img`"""

import sys

from .cli import main
from .exit_codes import FAILURE, INTERRUPTED

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        if "--debug" in sys.argv:
            raise
        sys.exit(INTERRUPTED)
    except (Exception, OSError) as e:
        if "--debug" in sys.argv:
            raise
        print(f"ERROR ({type(e).__name__}): {e}")
        sys.exit(FAILURE)
