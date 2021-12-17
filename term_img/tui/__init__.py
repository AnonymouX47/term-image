"""Term-Img's Terminal User Interface"""

from __future__ import annotations

import argparse
import logging
from typing import Iterable, Iterator, Tuple, Union

from . import main
from .widgets import Image


def init(
    args: argparse.Namespace,
    images: Iterable[Tuple[str, Union[Image, Iterator]]],
    contents: dict,
) -> None:
    """Initializes the TUI"""
    from ..logging import log

    global launched

    logger = logging.getLogger(__name__)
    log("Launching TUI", logger, logging.INFO, direct=False)

    launched = True
    main.max_pixels = args.max_pixels
    main.recursive = args.recursive
    main.show_hidden = args.all
    main.displayer = main.display_images(".", iter(images), contents, top_level=True)
    next(main.displayer)
    try:
        main.loop.run()
        log("Exited TUI normally", logger, logging.INFO, direct=False)
    finally:
        launched = False


launched = False
