"""Support for command-line execution using `python -m term-img`"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
